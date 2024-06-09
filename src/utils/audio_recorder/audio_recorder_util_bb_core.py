#!/bin/env python3
""" MQTT connected audio recorder for Blueberry

Wishes to be provided with {"id": identifier_of_this_audio_recorder_request: str} over MQTT to "bloob/{arguments.device_id}/cores/audio_recorder_util/record_speech"

Will respond with {"id": received_id: str, "audio": audio: str}, where audio is a WAV file, encoded as b64 bytes, then decoded into a string. To "bloob/{arguments.device_id}/cores/audio_recorder_util/finished"
"""
import json
import base64
import pathlib
import os

import paho.mqtt.publish as publish

default_temp_path = pathlib.Path("/dev/shm/bloob")
audio_recorder_temp_path = default_temp_path.joinpath("audio_recorder")

import pybloob

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 
default_audio_recorder_path = default_data_path.joinpath("audio_recorder")

if not os.path.exists(audio_recorder_temp_path):
  os.makedirs(audio_recorder_temp_path)

core_id = "audio_recorder_util"

arguments = pybloob.coreArgParse()
c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"))

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Audio Recorder",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/utils/audio_recorder",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Records audio from Pipewire",
    "version": "0.1",
    "license": "AGPLv3"
  }
}

c.publishConfig(core_config)

c.log("Starting up...")

#This is turned into a str because otherwise python-mpv and faster-whisper broke
recorded_audio_wav_path = str(audio_recorder_temp_path.joinpath("recorded_audio.wav"))

import numpy as np
import wave
## Set audio variables
channels = 1 # Mono since stereo would be a waste of data
sample_rate = 16000 # Also saves data, though it may be changed in the future
frame_size = 1280 # This value chosen because oww recommends 80ms frames, 16000/1280 = 12.5, 1000/12.5 = 80ms, and I just didn't change it for the recorder
vad_speech_margin_init = 12000 # The number of samples (normally 16000 for 1s) of "Not Speech" before the recording stops

vad_aggressiveness = 3 # 0-3, least to most aggressive at filtering noise

from pyaudio import PyAudio, paInt16
audio_recording_system = PyAudio()

import webrtcvad
vad = webrtcvad.Vad(vad_aggressiveness)

## Find the index for the device named "pipewire" to use Pipewire for resampling of the default device
audio_recording_system_info = audio_recording_system.get_host_api_info_by_index(0)
total_devices = audio_recording_system_info.get("deviceCount")
for device_index in range(total_devices):
  if audio_recording_system.get_device_info_by_host_api_device_index(0, device_index).get("name") == "pipewire":
    mic_index = audio_recording_system.get_device_info_by_host_api_device_index(0, device_index).get("index")
c.log(f"Found pipewire at index {mic_index}")

## Open Mic:
c.log("Opening Mic")
mic_stream = audio_recording_system.open(format=paInt16, channels=channels, rate=sample_rate, input=True, frames_per_buffer=frame_size, input_device_index=mic_index)

import paho.mqtt.subscribe as mqtt_subscribe
import paho.mqtt.publish as publish

while True:
  try:
    request_id = json.loads(mqtt_subscribe.simple(f"bloob/{arguments.device_id}/cores/audio_recorder_util/record_speech", hostname = arguments.host, port = arguments.port ).payload.decode())["id"]
    speech_buffer = []
  except json.decoder.JSONDecodeError:
    c.log("Recieved invalid JSON")
  while True:

    ## Begin capturing audio
    current_frame = np.frombuffer(mic_stream.read(frame_size), dtype=np.int16)

    # Record, stopping when no speech detected
    c.log("Recording: waiting for 1s of silence")
    vad_speech_margin = vad_speech_margin_init
    while vad_speech_margin > 0:
      current_frame = np.frombuffer(mic_stream.read(frame_size), dtype=np.int16)
      speech_buffer.extend(current_frame)

      ## Split 80ms frames in 4 (to 20ms frames) since webrtcvad requires smaller frames		
      for vad_little_frame in np.array_split(current_frame, 4):
        
        if vad.is_speech(vad_little_frame, sample_rate) == True:
          vad_speech_margin = vad_speech_margin_init
        else:
          vad_speech_margin -= 320

    c.log(f"Finished recording, saving audio to {recorded_audio_wav_path}")

    with wave.open(recorded_audio_wav_path, 'wb') as wf:
      wf.setnchannels(channels)
      wf.setsampwidth(audio_recording_system.get_sample_size(paInt16))
      wf.setframerate(sample_rate)
      wf.writeframes(b''.join(speech_buffer))

    with open(recorded_audio_wav_path, 'rb') as wf:
      audio_to_send = base64.b64encode(wf.read()).decode()

    c.log("Saved audio")
    publish.single(topic = f"bloob/{arguments.device_id}/cores/audio_recorder_util/finished", payload= json.dumps({"id": request_id, "audio" : audio_to_send}), hostname = arguments.host, port = arguments.port, qos=1)
    break