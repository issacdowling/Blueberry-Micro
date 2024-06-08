#!/bin/env python3
""" MQTT connected STT engine for Blueberry, making use of OpenAI Whisper, through faster-whisper

Wishes to be provided with {"id": identifier_of_this_tts_request: str, "audio": text_to_speak: str}, where audio is a WAV file, encoded as b64 bytes, then decoded into a string, over MQTT to "bloob/{arguments.device_id}/cores/stt_util/transcribe"

Will respond with {"id", id: str, "text": transcript} to "bloob/{arguments.device_id}/cores/stt_util/finished"
"""
import argparse
import paho.mqtt.client as mqtt
import sys
import json
import base64
import pathlib
import os

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

default_temp_path = pathlib.Path("/dev/shm/bloob")
stt_temp_path = default_temp_path.joinpath("stt")

import pybloob

from faster_whisper import WhisperModel

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 
default_stt_path = default_data_path.joinpath("stt")

if not os.path.exists(default_stt_path):
  os.makedirs(default_stt_path, exist_ok=True)

transcribed_audio_path = stt_temp_path.joinpath("transcribed_audio.wav")

if not os.path.exists(stt_temp_path):
  os.makedirs(stt_temp_path)

arguments = pybloob.coreArgParse()




core_id = "stt_util"

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "STT",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/utils/stt",
    "author": None,
    "icon": None,
    "description": "Transcribes speech using Faster Whisper",
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

## Get device configs from central config, instantiate
pybloob.log("Getting Centralised Config from Orchestrator", log_data)
print(f"bloob/{arguments.device_id}/{core_id}/central_config")
central_config = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/central_config", hostname=arguments.host, port=arguments.port).payload.decode())

if not os.path.exists(default_data_path):
  pybloob.log("Creating STT path", log_data)
  os.makedirs(default_data_path)

pybloob.log(f"Loading Model: {central_config['model']}", log_data)

# Do this so that unfound models are automatically downloaded, but by default we aren't checking remotely at all, and the
# STT directory doesn't need to be deleted just to automatically download other models
try:
  model = WhisperModel(model_size_or_path=central_config['model'], device="cpu", download_root=default_stt_path, local_files_only = True)
except: #huggingface_hub.utils._errors.LocalEntryNotFoundError (but can't do that here since huggingfacehub not directly imported)
  pybloob.log(f"Downloading Model: {central_config['model']}", log_data)
  model = WhisperModel(model_size_or_path=central_config['model'], device="cpu", download_root=default_stt_path)

pybloob.log(f"Loaded Model: {central_config['model']}", log_data)


def transcribe(audio): 
  # TODO: Send audio to STT directly rather than using a file for it. Still record audio to /dev/shm for option to replay
  # TODO: Figure out why large models (distil and normal) cause this to significantly slow down, where any other model does it instantly
  # across significantly different tiers of hardware
  segments, info = model.transcribe(audio, beam_size=5, condition_on_previous_text=False) #condition_on_previous_text=False reduces hallucinations and inference time with no downsides for our short text.

  pybloob.log("Transcribing...", log_data)
  
  raw_spoken_words = ""
  for segment in segments:
    raw_spoken_words += segment.text
  pybloob.log(f"Transcribed words: {raw_spoken_words}", log_data)

  return raw_spoken_words

def on_message(client, _, message):
  try:
    pybloob.log("Waiting for input...", log_data)
    msg_json = json.loads(message.payload.decode())
    with open(transcribed_audio_path,'wb+') as audio_file:
      #Encoding is like this because the string must first be encoded back into the base64 bytes format, then decoded again, this time as b64, into the original bytes.
      audio_file.write(base64.b64decode(msg_json["audio"].encode()))
    
    transcription = transcribe(str(transcribed_audio_path))
  except KeyError:
    pybloob.log("Couldn't find the correct keys in recieved JSON", log_data)
  pybloob.log("Publishing output", log_data)
  stt_mqtt.publish(f"bloob/{arguments.device_id}/cores/stt_util/finished", json.dumps({"id": msg_json["id"], "text": transcription}), qos=1)

stt_mqtt = mqtt.Client()
stt_mqtt.connect(arguments.host, arguments.port)
stt_mqtt.on_message = on_message

stt_mqtt.subscribe(f"bloob/{arguments.device_id}/cores/stt_util/transcribe")


stt_mqtt.loop_forever()