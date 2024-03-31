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

bloob_python_module_dir = pathlib.Path(__file__).parents[1].joinpath("python_module")
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

resources_dir = src_folder_dir.joinpath("resources")

with open(data_dir.joinpath("config.json"), 'r') as conf_file:
	config_json = json.load(conf_file)


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

log("Loading Cores", log_data)
collections = []
## Load Cores
for core_file in external_core_files + internal_core_files + util_files:
	print(f"Attempting to load {core_file}")
	core_obj = core.Core(path=core_file, host=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"], devid=config_json["uuid"])

	if not core_obj.is_collection_handler:
		if core_obj.is_util:
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

# Detection loop
while True:
	log("Waiting for wakeword...", log_data)

	request_identifier = str(randint(1000,9999))

	#Wait for wakeword
	subscribe.simple(f"bloob/{config_json['uuid']}/wakeword/detected", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
	log("Wakeword detected, starting recording", log_data)

	#Play sound for...
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
	log(f"Parsing finished - {parsed_json['text']} - sending to core", log_data)

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