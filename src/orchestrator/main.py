import pathlib
import os
import subprocess
import json
import atexit
from time import sleep
import paho.mqtt.publish as publish
import paho.mqtt.subscribe as subscribe
import pathlib


def exit_cleanup():
  for core in loaded_cores:
    list(core.values())[0].kill()
atexit.register(exit_cleanup)

data_dir = pathlib.Path(os.environ["HOME"]).joinpath(".config/bloob")


with open(data_dir.joinpath("config.json"), 'r') as config_file:
  config_json = json.load(config_file)


cores_dir = data_dir.joinpath("cores")
parent_folder_dir = pathlib.Path(__file__).parents[1]

builtin_cores = []
builtin_cores.extend([parent_folder_dir.joinpath("audio_playback/main.py"), parent_folder_dir.joinpath("audio_recorder/main.py"), parent_folder_dir.joinpath("stt/main.py"), parent_folder_dir.joinpath("tts/main.py"), parent_folder_dir.joinpath("wakeword/main.py")])
external_core_files = [str(core) for core in cores_dir.glob('*bb_core*')] + builtin_cores
loaded_cores = []


for core_file in external_core_files:
  print(f"Attempting to load {core_file}")
  core_run = subprocess.run([core_file, "--identify", "true"],capture_output=True)
  core_json = json.loads(core_run.stdout.decode())
  loaded_cores.append({core_json["id"]: subprocess.Popen([core_file, "--host", config_json["mqtt"]["host"], "--port", str(config_json["mqtt"]["port"]), "--device-id", config_json["uuid"]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)})

  print(f"Loaded {core_json['id']}")

sleep(1)

# Detection loop
while True:
  print("Waiting for wakeword...")

  #Wait for wakeword
  subscribe.simple(f"bloob/{config_json['uuid']}/wakeword/detected", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
  print("Wakeword detected, starting recording")

  #Start recording
  publish.single(f"bloob/{config_json['uuid']}/audio_recorder/record_speech", payload=json.dumps({"id": 1}) ,hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
  #Receieve recording
  recording = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/audio_recorder/finished", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload)["audio"]
  print("Recording finished, starting transcription")

  #Transcribe
  publish.single(f"bloob/{config_json['uuid']}/stt/transcribe", payload=json.dumps({"id": 1, "audio": recording}), hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"])
  #Receive transcription
  transcript = json.loads(subscribe.simple(f"bloob/{config_json['uuid']}/stt/finished", hostname=config_json["mqtt"]["host"], port=config_json["mqtt"]["port"]).payload)["text"]
  print(f"Transcription finished - {transcript} - starting intent recognition")



input()