#!/bin/env python3
""" MQTT connected Wakeword engine for Blueberry, making use of OpenWakeWord

Requires no input, will always be detecting.

Will respond with {"wakeword_id": id_of_detected_wakeword: str, "confidence": confidence_of_detection: str} to "bloob/{arguments.device_id}/wakeword/detected"
"""
import argparse
import subprocess
import asyncio
import aiomqtt
import sys
import re
import json
import base64
import pathlib
import os
import paho.mqtt.publish as publish

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 
default_ww_path = default_data_path.joinpath("ww")

default_temp_path = pathlib.Path("/dev/shm/bloob")
ww_temp_path = default_temp_path.joinpath("ww")

if not os.path.exists(ww_temp_path):
  os.makedirs(ww_temp_path)

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")
arg_parser.add_argument('--ww-path', default=default_ww_path)
arg_parser.add_argument('--ww-model', default="en_US-lessac-high")
arguments = arg_parser.parse_args()

# Create Wakeword data directory if necessary
if not os.path.exists(arguments.ww_path):
  print("Creating Wakeword Data Directory")
  os.makedirs(arguments.ww_path)

#This is turned into a str because otherwise python-mpv and faster-whisper broke
detected_speech_wav_path = str(ww_temp_path.joinpath("detected_speech.wav"))
## TODO: Eventually get this list from the server
## TODO: Allow certain actions to be performed solely from saying certain wakewords (split into "wake"words and "action"words or something)
## Loads all .tflite custom models in the wakeword folder
print(f"Found these OpenWakeWord Models: {[str(model) for model in arguments.ww_path.glob('*.tflite')]}")
enabled_wakewords = [str(model) for model in arguments.ww_path.glob('*.tflite')]
## TODO: Add automatically downloading "personal wakewords" from configuration server and enabling them


## Load OpenWakeword #######################
from openwakeword import Model
from pyaudio import PyAudio, paInt16
import numpy as np
import wave

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
print(f"Found pipewire at index {mic_index}")

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
print("Opening Mic")
mic_stream = audio_recording_system.open(format=paInt16, channels=channels, rate=sample_rate, input=True, frames_per_buffer=frame_size, input_device_index=mic_index)


## Detection loop
print("Waiting for wakeword:")
while True:

  ## Begin capturing audio
  current_frame = np.frombuffer(mic_stream.read(frame_size), dtype=np.int16)

  # Attempt detection: if fails, loop
  prediction = oww.predict(current_frame)
  for model_name in prediction.keys():
    confidence = prediction[model_name]
    ## Upon detection:
    if confidence >= 0.5:

      publish.single(topic = f"bloob/{arguments.device_id}/wakeword/detected", payload = json.dumps({"wakeword_id": model_name, "confidence": str(prediction[model_name])}), hostname = arguments.host, port = arguments.port)
      print(f"Wakeword Detected: {model_name}, with confidence of {prediction[model_name]}")
      ### Feeds silence for "4 seconds" to OpenWakeWord so that it doesn't lead to repeat activations
      ### See for yourself: https://github.com/dscripka/openWakeWord/issues/37
      ### Don't disable or it will lead to approximately 2 hours and 23 minutes of confusion.
      oww.predict(np.zeros(sample_rate*4, np.int16))