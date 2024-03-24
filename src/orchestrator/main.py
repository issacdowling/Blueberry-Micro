import pathlib
import os
import subprocess
import json
import atexit
from time import sleep
import paho.mqtt.publish as publish
import paho.mqtt.subscribe as subscribe
import pathlib
from random import randint


def exit_cleanup():
  for core in loaded_cores:
    list(core.values())[0].kill()
  for core in loaded_utils:
    list(core.values())[0].kill()
atexit.register(exit_cleanup)

data_dir = pathlib.Path(os.environ["HOME"]).joinpath(".config/bloob")


with open(data_dir.joinpath("config.json"), 'r') as config_file:
  config_json = json.load(config_file)


cores_dir = data_dir.joinpath("cores")
parent_folder_dir = pathlib.Path(__file__).parents[1]

util_files = []
util_files.extend([parent_folder_dir.joinpath("utils/audio_playback/main.py"), parent_folder_dir.joinpath("utils/audio_recorder/main.py"), parent_folder_dir.joinpath("utils/stt/main.py"), parent_folder_dir.joinpath("utils/tts/main.py"), parent_folder_dir.joinpath("utils/wakeword/main.py"), parent_folder_dir.joinpath("utils/intent_parser/main.py")])
external_core_files = [str(core) for core in cores_dir.glob('*bb_core*')]
loaded_utils = []
loaded_cores = []


for util_file in util_files:
  print(f"Attempting to load {util_file}")
  util_run = subprocess.run([util_file, "--identify", "true"],capture_output=True)
  util_json = json.loads(util_run.stdout.decode())
  loaded_utils.append({util_json["id"]: subprocess.Popen([util_file, "--host", config_json["mqtt"]["host"], "--port", str(config_json["mqtt"]["port"]), "--device-id", config_json["uuid"]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)})

  print(f"Loaded Util: {util_json['id']}")


for core_file in external_core_files:
  print(f"Attempting to load {core_file}")
  core_run = subprocess.run([core_file, "--identify", "true"],capture_output=True)
  core_json = json.loads(core_run.stdout.decode())
  loaded_cores.append({core_json["id"]: subprocess.Popen([core_file, "--host", config_json["mqtt"]["host"], "--port", str(config_json["mqtt"]["port"]), "--device-id", config_json["uuid"]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)})

  print(f"Loaded Core: {core_json['id']}")

sleep(1)

# Detection loop
while True:
  print("Waiting for wakeword...")

  request_identifier = str(randint(1000,9999))

  #Wait for wakeword
  subscribe.simple(f"bloob/{config_json['uuid']}/wakeword/detected", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
  print("Wakeword detected, starting recording")

  #Start recording
  publish.single(f"bloob/{config_json['uuid']}/audio_recorder/record_speech", payload=json.dumps({"id": request_identifier}) ,hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
  #Receieve recording
  recording = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/audio_recorder/finished", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload)["audio"]
  print("Recording finished, starting transcription")

  #Transcribe
  publish.single(f"bloob/{config_json['uuid']}/stt/transcribe", payload=json.dumps({"id": request_identifier, "audio": recording}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
  #Receive transcription
  transcript = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/stt/finished", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload)["text"]
  print(f"Transcription finished - {transcript} - starting intent recognition")

  #Parse
  publish.single(f"bloob/{config_json['uuid']}/intent_parser/run", payload=json.dumps({"id": request_identifier, "text": transcript}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
  print("sent to parser, waiting to receieve")
  #Receieve parsed intent
  parsed_json = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/intent_parser/finished", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload.decode())
  
  print(transcript, parsed_json["intent"], parsed_json["core"])

input()