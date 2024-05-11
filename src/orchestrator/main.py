import pathlib
import os
import subprocess
import json
from time import sleep
import paho.mqtt.publish as publish
import paho.mqtt.subscribe as subscribe
import pathlib
import base64
from random import randint
import sys
import signal
import traceback

import core

# Write info, such as path, to a file for others to access
bloob_temp_path = pathlib.Path("/dev/shm/bloob/")
bloob_install_info_path = bloob_temp_path.joinpath("bloobinfo.txt")
os.makedirs(bloob_temp_path, exist_ok=True)

install_info = {
	"version": "0.1",
	"install_path": str(pathlib.Path(__file__).parents[2])
}

with open(bloob_install_info_path, "w") as install_info_file:
	json.dump(install_info, install_info_file)

bloob_python_module_dir = pathlib.Path(install_info["install_path"]).joinpath("src").joinpath("python_module")
sys.path.append(str(bloob_python_module_dir))

from bloob import getDeviceMatches, getTextMatches, log

## Allow graceful exits with MQTT stuff handled
def exit_cleanup(*args):
	log("Shutting down...", log_data)
	#For each core, clear the retained message for the centralised config
	for core in loaded_cores:
		publish.single(f"bloob/{config_json['uuid']}/cores/{core.core_id}/central_config", payload=None, retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
	#For each collection, clear the retained message
	for collection in collections:
		publish.single(f"bloob/{config_json['uuid']}/collections/{collection['id']}", payload=None, retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
	#Clear the retained list of collections
	publish.single(f"bloob/{config_json['uuid']}/collections/list", payload=None, retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])

	#Clear the recording topic
	publish.single(f"bloob/{config_json['uuid']}/recording", payload=None, retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
	#Clear the thinking topic
	publish.single(f"bloob/{config_json['uuid']}/thinking", payload=None, retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])

	#Kill cores
	for core in loaded_cores:
		core.stop()
	for util in loaded_utils:
		util.stop()
	#Clear the retained cores/list message
	publish.single(f"bloob/{config_json['uuid']}/cores/list", payload=None, retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
	exit()

signal.signal(signal.SIGTERM, exit_cleanup)
signal.signal(signal.SIGINT, exit_cleanup)

## Set up directories
data_dir = pathlib.Path(os.environ["HOME"]).joinpath(".config/bloob")

cores_dir = data_dir.joinpath("cores")
src_folder_dir = pathlib.Path(__file__).parents[1]

config_path = data_dir.joinpath("config.json")

resources_dir = src_folder_dir.joinpath("resources")

## Make default - or load custom - config
if not os.path.exists(data_dir):
	os.mkdir(data_dir)

if os.path.exists(config_path):
	with open(config_path, 'r') as conf_file:
		config_json = json.load(conf_file)
else:
	config_json = {
    "instance_name": "Default Name",
    "uuid": "test",
    "stt_model": "Systran/faster-distil-whisper-small.en",
    "tts_model": "en_GB-southern_english_female-low",
    "external_core_ids": [],
    "mqtt": {
        "host": "localhost",
        "port": 1883,
        "user": "",
        "password": ""
    }
}
	with open(data_dir.joinpath("config.json"), 'w') as conf_file:
		json.dump(config_json, conf_file)

## Logging begins here
core_id = "orchestrator"
log_data = config_json["mqtt"]["host"], config_json["mqtt"]["port"], config_json["uuid"], core_id
log("Starting up...", log_data)

util_files = []
util_files.extend([src_folder_dir.joinpath("utils/audio_playback/main.py"), src_folder_dir.joinpath("utils/audio_recorder/main.py"), src_folder_dir.joinpath("utils/stt/main.py"), src_folder_dir.joinpath("utils/tts/main.py"), src_folder_dir.joinpath("utils/wakeword/main.py"), src_folder_dir.joinpath("utils/intent_parser/main.py")])
external_core_files = [str(core) for core in cores_dir.glob('**/*bb_core*')]
internal_core_files = [str(core) for core in src_folder_dir.glob('**/*bb_core*')]
loaded_utils = []
loaded_cores = []

log("Loading Start/Stop recording audio files", log_data)
## Load the start and stop listening files (TODO: Allow their paths to be changed in the config)
with open(resources_dir.joinpath("audio/begin_listening.wav"), "rb") as audio_file:
	begin_listening_audio = base64.b64encode(audio_file.read()).decode()
with open(resources_dir.joinpath("audio/stop_listening.wav"), "rb") as audio_file:
	stop_listening_audio = base64.b64encode(audio_file.read()).decode()
with open(resources_dir.joinpath("audio/instant_intent.wav"), "rb") as audio_file:
	instant_intent_audio = base64.b64encode(audio_file.read()).decode()
with open(resources_dir.joinpath("audio/error.wav"), "rb") as audio_file:
	error_audio = base64.b64encode(audio_file.read()).decode()

log("Loading Cores", log_data)
collections = []
## Load Cores
for core_file in external_core_files + internal_core_files + util_files:
	print(f"Attempting to load {core_file}")
	core_obj = core.Core(path=core_file, host=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"], devid=config_json["uuid"])

	if not core_obj.is_collection_handler:
		if core_obj.is_util:
			if(core_obj.core_id == "tts" and config_json.get("tts_model") != None):
				core_obj.extra_args.append("--tts-model")
				core_obj.extra_args.append(config_json.get("tts_model"))
			if(core_obj.core_id == "stt" and config_json.get("stt_model") != None):
				core_obj.extra_args.append("--stt-model")
				core_obj.extra_args.append(config_json.get("stt_model"))
			loaded_utils.append(core_obj)
			log(f"Loaded util: {core_obj.core_id}", log_data)
		else:
			loaded_cores.append(core_obj)
			log(f"Loaded core: {core_obj.core_id}", log_data)

	elif core_obj.is_collection_handler:
		collections += core_obj.get_collections()
		log(f"Loaded collection_handler: {core_obj.core_id}", log_data)
		
	core_obj.run()


all_collection_ids = [collection["id"] for collection in collections]

for collection in collections:
	log(f"Publishing Collection: {collection['id']}", log_data)
	publish.single(f"bloob/{config_json['uuid']}/collections/{collection['id']}", payload=json.dumps(collection), retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])

log(f"Publishing list of Collections: {collection['id']}", log_data)
publish.single(f"bloob/{config_json['uuid']}/collections/list", payload=json.dumps({"loaded_collections": all_collection_ids}), retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])

# If there are no external cores, just set the core IDs to those of the Orchestrated cores. If there are some, add those to the list too
all_core_ids = [core.core_id for core in loaded_cores] if config_json.get("external_core_ids") == None else [core.core_id for core in loaded_cores] + config_json["external_core_ids"]

log(f"Publishing list of Cores: {collection['id']}", log_data)
#Publish and retain loaded cores for access over MQTT
publish.single(f"bloob/{config_json['uuid']}/cores/list", payload=json.dumps({"loaded_cores": all_core_ids}), retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])

#For each core, publish the JSON object under the key of the core id, to allow centralised configs where wanted.
for core in loaded_cores:
	log(f"Publishing central Core config for: {core.core_id}", log_data)
	publish.single(f"bloob/{config_json['uuid']}/cores/{core.core_id}/central_config", payload=json.dumps(config_json.get(core.core_id)), retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])


# Find all intents, extract their wakewords, and create a list of wakewords that skip straight to the intent parser
log("Loading intents to get which wakewords to treat specially", log_data)
instant_intent_words = []
for core_id in all_core_ids:
	log(f"Getting Config for {core_id}", log_data)
	core_intents = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/cores/{core_id}/config",hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload.decode()).get("intents")
	for intent in core_intents:
		if intent.get("wakewords"):
			for wakeword in intent["wakewords"]:
				instant_intent_words.append(wakeword)

if len(instant_intent_words) > 0:
	log(f"Registered Instant Intent words: {instant_intent_words}", log_data)
else:
	log(f"No Instant Intent words registered", log_data)


# Detection loop
while True:
	log("Waiting for wakeword...", log_data)

	request_identifier = str(randint(1000,9999))

	#Wait for wakeword
	wakeword = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/wakeword/detected", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload.decode())["wakeword_id"]
	log(f"Wakeword {wakeword} detected", log_data)

	if wakeword in instant_intent_words:
		log(f"Executing Instant Intent", log_data)
		#Play sound for starting recording
		publish.single(f"bloob/{config_json['uuid']}/audio_playback/play_file", payload=json.dumps({"id": request_identifier, "audio": instant_intent_audio}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
		transcript = wakeword

		#Publish the fact that we're processing the request (thinking)
		publish.single(f"bloob/{config_json['uuid']}/thinking", payload=json.dumps({"is_thinking": True}), retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])

	else:
		log(f"Starting recording", log_data)
		#Publish the fact that we're now recording
		publish.single(f"bloob/{config_json['uuid']}/recording", payload=json.dumps({"is_recording": True}), retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
		#Play sound for starting recording
		publish.single(f"bloob/{config_json['uuid']}/audio_playback/play_file", payload=json.dumps({"id": request_identifier, "audio": begin_listening_audio}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
		#Start recording
		publish.single(f"bloob/{config_json['uuid']}/audio_recorder/record_speech", payload=json.dumps({"id": request_identifier}) ,hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
		#Receieve recording
		received_id = None
		while received_id != request_identifier:
			recording_json = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/audio_recorder/finished", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload)
			received_id = recording_json["id"]
		#Play sound for finished recording
		publish.single(f"bloob/{config_json['uuid']}/audio_playback/play_file", payload=json.dumps({"id": request_identifier, "audio": stop_listening_audio}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
		recording = recording_json["audio"]
		log("Recording finished, starting transcription", log_data)

		#Publish the fact that we're no longer recording
		publish.single(f"bloob/{config_json['uuid']}/recording", payload=json.dumps({"is_recording": False}), retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])

		#Publish the fact that we're processing the request (thinking)
		publish.single(f"bloob/{config_json['uuid']}/thinking", payload=json.dumps({"is_thinking": True}), retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])

		#Transcribe
		publish.single(f"bloob/{config_json['uuid']}/stt/transcribe", payload=json.dumps({"id": request_identifier, "audio": recording}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
		#Receive transcription
		received_id = None
		while received_id != request_identifier:
			stt_json = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/stt/finished", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload)
			received_id = stt_json["id"]
		transcript = stt_json["text"]
		log(f"Transcription finished - {transcript} - sending to intent parser", log_data)

	#Parse
	publish.single(f"bloob/{config_json['uuid']}/intent_parser/run", payload=json.dumps({"id": request_identifier, "text": transcript}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
	#Receieve parsed intent
	received_id = None
	while received_id != request_identifier:
		parsed_json = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/intent_parser/finished", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload.decode())
		received_id = parsed_json["id"]
	log(f"Parsing finished - {parsed_json['text']} - sending to core ({parsed_json['core_id']} - {parsed_json['intent']})", log_data)

	# Handle the intent not being recognised by saying that we didn't understand
	if not (parsed_json["core_id"] == None or parsed_json["intent"] == None):
		#Fire intent to relevant core
		publish.single(f"bloob/{config_json['uuid']}/cores/{parsed_json['core_id']}/run", payload=json.dumps({"id": request_identifier, "intent": parsed_json['intent'], "text": parsed_json['text']}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"], client_id="bloob-orchestrator")
		#Get output from the core
		received_id = None
		while received_id != request_identifier:
			core_json = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/cores/{parsed_json['core_id']}/finished", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"], client_id="bloob-orchestrator").payload.decode())
			received_id = core_json["id"]
		speech_text = core_json["text"]
		explanation = core_json["explanation"]
		log(f"Core finished - {speech_text} - sending to TTS", log_data)
	else:
		log("Didn't receive an Intent", log_data)
		speech_text = "I'm not sure what you mean, could you repeat that?"
		explanation = "Failed to recognise what the user meant"

	#Publish the fact that we're no longer processing the request (thinking)
	publish.single(f"bloob/{config_json['uuid']}/thinking", payload=json.dumps({"is_thinking": False}), retain=True, hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])

	#Text to speech the core's output
	publish.single(f"bloob/{config_json['uuid']}/tts/run", payload=json.dumps({"id": request_identifier, "text": speech_text}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
	#Get TTS output
	received_id = None
	while received_id != request_identifier:
		tts_json = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/tts/finished", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload.decode())
		received_id = tts_json["id"]
	tts_audio = tts_json["audio"]
	log(f"TTS finished - sending to audio_playback", log_data)

	#Send to audio playback util
	publish.single(f"bloob/{config_json['uuid']}/audio_playback/play_file", payload=json.dumps({"id": request_identifier, "audio": tts_audio}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])