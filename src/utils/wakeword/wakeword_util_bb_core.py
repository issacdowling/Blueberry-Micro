#!/bin/env python3
""" MQTT connected Wakeword engine for Blueberry, making use of OpenWakeWord

Requires no input, will always be detecting.

Will respond with {"wakeword_id": id_of_detected_wakeword: str, "confidence": confidence_of_detection: str} to "bloob/{arguments.device_id}/cores/wakeword_util/detected"
"""
import sys
import json
import pathlib
import os
import paho.mqtt.publish as publish

default_temp_path = pathlib.Path("/dev/shm/bloob")
ww_temp_path = default_temp_path.joinpath("ww")

bloobinfo_path = default_temp_path.joinpath("bloobinfo.txt")
with open(bloobinfo_path, "r") as bloobinfo_file:
  bloob_info = json.load(bloobinfo_file)

bloob_python_module_dir = pathlib.Path(bloob_info["install_path"]).joinpath("src").joinpath("python_module")
sys.path.append(str(bloob_python_module_dir))

import pybloob

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 
default_ww_path = default_data_path.joinpath("ww")

if not os.path.exists(ww_temp_path):
  os.makedirs(ww_temp_path)

arguments = pybloob.coreArgParse()

core_id = "wakeword_util"

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "TTS",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/utils/tts",
    "author": None,
    "icon": None,
    "description": "Speaks text",
    "version": "0.1",
    "license": "AGPLv3"
  }
}

publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, hostname=arguments.host, port=arguments.port)

# Clears the published config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
import signal
def on_exit(*args):
  pybloob.log("Shutting Down...", log_data)
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
  exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

## Logging starts here
log_data = arguments.host, int(arguments.port), arguments.device_id, core_id
pybloob.log("Starting up...", log_data)

# Create Wakeword data directory if necessary
if not os.path.exists(default_ww_path):
  pybloob.log(f"Creating Wakeword path: {default_ww_path}", log_data)
  os.makedirs(default_ww_path)

#This is turned into a str because otherwise python-mpv and faster-whisper broke
detected_speech_wav_path = str(ww_temp_path.joinpath("detected_speech.wav"))
## TODO: Eventually get this list from the server
## TODO: Allow certain actions to be performed solely from saying certain wakewords (split into "wake"words and "action"words or something)
## Loads all .tflite custom models in the wakeword folder
pybloob.log(f"Found these OpenWakeWord Models: {[str(model) for model in default_ww_path.glob('*.tflite')]}", log_data)
enabled_wakewords = [str(model) for model in default_ww_path.glob('*.tflite')]
## TODO: Add automatically downloading "personal wakewords" from configuration server and enabling them

if len(enabled_wakewords) == 0:
  pybloob.log(f"There are no wakewords in {default_ww_path}, so wakeword detection cannot continue. Exiting.", log_data)
  exit()

## Load OpenWakeword #######################
from openwakeword import Model
from pyaudio import PyAudio, paInt16
import numpy as np

## Set audio variables
channels = 1 # Mono since stereo would be a waste of data
sample_rate = 16000 # Required by OpenWakeWord
frame_size = 1280 # This value chosen because oww recommends 80ms frames, 16000/1280 = 12.5, 1000/12.5 = 80ms

audio_recording_system = PyAudio()

## Find the index for the device named "pipewire" to use Pipewire for resampling of the default device
audio_recording_system_info = audio_recording_system.get_host_api_info_by_index(0)
total_devices = audio_recording_system_info.get("deviceCount")
for device_index in range(total_devices):
  if audio_recording_system.get_device_info_by_host_api_device_index(0, device_index).get("name") == "pipewire":
    mic_index = audio_recording_system.get_device_info_by_host_api_device_index(0, device_index).get("index")
pybloob.log(f"Found pipewire at index {mic_index}", log_data)

### Load OpenWakeWord model
## If melspectrogram not found (first launch), download then continue
try:
  oww = Model(wakeword_models=enabled_wakewords, inference_framework = "tflite")
except ValueError:
  from openwakeword import utils
  utils.download_models(["melspectrogram.tflite"])
  oww = Model(wakeword_models=enabled_wakewords, inference_framework = "tflite")

speech_buffer = []

## Open Mic:
pybloob.log("Opening Mic", log_data)
mic_stream = audio_recording_system.open(format=paInt16, channels=channels, rate=sample_rate, input=True, frames_per_buffer=frame_size, input_device_index=mic_index)


## Detection loop
pybloob.log("Waiting for wakeword:", log_data)
while True:
  speech_buffer = []
  ## Begin capturing audio
  current_frame = np.frombuffer(mic_stream.read(frame_size), dtype=np.int16)

  # Attempt detection: if fails, loop
  prediction = oww.predict(current_frame)
  for model_name in prediction.keys():
    confidence = prediction[model_name]
    ## Upon detection:
    if confidence >= 0.6:

      publish.single(topic = f"bloob/{arguments.device_id}/cores/wakeword_util/finished", payload = json.dumps({"wakeword_id": model_name, "confidence": str(prediction[model_name])}), hostname = arguments.host, port = arguments.port, qos=1)
      pybloob.log(f"Wakeword Detected: {model_name}, with confidence of {prediction[model_name]}", log_data)
      ### Feeds silence for "4 seconds" to OpenWakeWord so that it doesn't lead to repeat activations
      ### See for yourself: https://github.com/dscripka/openWakeWord/issues/37
      ### Don't disable or it will lead to approximately 2 hours and 23 minutes of confusion.
      oww.predict(np.zeros(sample_rate*4, np.int16))