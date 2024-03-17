""" MQTT connected STT engine for Blueberry, making use of OpenAI Whisper, through faster-whisper

Wishes to be provided with {"id": identifier_of_this_tts_request: str, "audio": text_to_speak: str}, where audio is a WAV file, encoded as b64 bytes, then decoded into a string, over MQTT to "bloob/{arguments.device_id}/stt/transcribe"
"""
import argparse
import subprocess
import asyncio
import paho.mqtt.client as mqtt
import sys
import re
import json
import base64
import pathlib
import os

from faster_whisper import WhisperModel

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 
default_stt_path = default_data_path.joinpath("stt")

default_temp_path = pathlib.Path("/dev/shm/bloob")
stt_temp_path = default_temp_path.joinpath("stt")

transcribed_audio_path = stt_temp_path.joinpath("transcribed_audio.wav")

if not os.path.exists(stt_temp_path):
  os.makedirs(stt_temp_path)

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")
arg_parser.add_argument('--stt-path', default=default_stt_path)
arg_parser.add_argument('--stt-model', default="Systran/faster-distil-whisper-small.en")
arguments = arg_parser.parse_args()

if not os.path.exists(arguments.stt_path):
  os.makedirs(arguments.stt_path)

print(f"Loading Model: {arguments.stt_model}")

# Do this so that unfound models are automatically downloaded, but by default we aren't checking remotely at all, and the
# STT directory doesn't need to be deleted just to automatically download other models
try:
  model = WhisperModel(model_size_or_path=arguments.stt_model, device="cpu", download_root=arguments.stt_path, local_files_only = True)
except: #huggingface_hub.utils._errors.LocalEntryNotFoundError (but can't do that here since huggingfacehub not directly imported)
  print(f"Downloading Model: {arguments.stt_model}")
  model = WhisperModel(model_size_or_path=arguments.stt_model, device="cpu", download_root=arguments.stt_path)

print(f"Loaded Model: {arguments.stt_model}")


def transcribe(audio): 
  # TODO: Send audio to STT directly rather than using a file for it. Still record audio to /dev/shm for option to replay
  # TODO: Figure out why large models (distil and normal) cause this to significantly slow down, where any other model does it instantly
  # across significantly different tiers of hardware
  segments, info = model.transcribe(audio, beam_size=5, condition_on_previous_text=False) #condition_on_previous_text=False reduces hallucinations and inference time with no downsides for our short text.

  print("Transcribing...")
  raw_spoken_words = ""
  for segment in segments:
    raw_spoken_words += segment.text
  print(f"Transcribed words: {raw_spoken_words}")

  return raw_spoken_words

def on_message(client, _, message):
  try:
    msg_json = json.loads(message.payload.decode())
    with open(transcribed_audio_path,'wb+') as audio_file:
      #Encoding is like this because the string must first be encoded back into the base64 bytes format, then decoded again, this time as b64, into the original bytes.
      audio_file.write(base64.b64decode(msg_json["audio"].encode()))
    
    transcription = transcribe(str(transcribed_audio_path))
  except KeyError:
    print("Couldn't find the correct keys in recieved JSON")

  stt_mqtt.publish(f"bloob/{arguments.device_id}/stt/finished", json.dumps({"id": msg_json["id"], "text": transcription}))

stt_mqtt = mqtt.Client()
stt_mqtt.connect(arguments.host, arguments.port)
stt_mqtt.on_message = on_message

# stt_mqtt.subscribe(f"bloob/{arguments.device_id}/tts/finished") # This is for testing, automatically transcribing what's recorded / said by TTS
stt_mqtt.subscribe(f"bloob/{arguments.device_id}/stt/transcribe")


stt_mqtt.loop_forever()