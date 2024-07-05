#!/bin/env python3
""" MQTT connected STT engine for Blueberry, making use of OpenAI Whisper, through faster-whisper

Wishes to be provided with {"id": identifier_of_this_tts_request: str, "audio": text_to_speak: str}, where audio is a WAV file, encoded as b64 bytes, then decoded into a string, over MQTT to "bloob/{arguments.device_id}/cores/stt_util/transcribe"

Will respond with {"id", id: str, "text": transcript} to "bloob/{arguments.device_id}/cores/stt_util/finished"
"""
import paho.mqtt.client as mqtt
import json
import base64
import pathlib
import os

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

default_temp_path = pathlib.Path("/dev/shm/bloob")
stt_temp_path = default_temp_path.joinpath("stt")

import pybloob

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 
default_stt_path = default_data_path.joinpath("stt")

if not os.path.exists(default_stt_path):
  os.makedirs(default_stt_path, exist_ok=True)

transcribed_audio_path = stt_temp_path.joinpath("transcribed_audio.wav")

if not os.path.exists(stt_temp_path):
  os.makedirs(stt_temp_path)

core_id = "stt_util"

arguments = pybloob.coreArgParse()
c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"))

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

c.publishConfig(core_config)

c.log("Starting up...")

## Get device configs from central config, instantiate
c.log("Getting Centralised Config from Orchestrator")
print(f"bloob/{arguments.device_id}/{core_id}/central_config")
central_config = c.getCentralConfig()

if central_config["mode"] == "local":
  c.log("Running STT locally")
  # Dynamic import so this isn't necessary to install on machines running this remotely
  from faster_whisper import WhisperModel

  if not os.path.exists(default_data_path):
    c.log("Creating STT path")
    os.makedirs(default_data_path)

  c.log(f"Loading Model: {central_config['model']}")

  # Do this so that unfound models are automatically downloaded, but by default we aren't checking remotely at all, and the
  # STT directory doesn't need to be deleted just to automatically download other models
  try:
    model = WhisperModel(model_size_or_path=central_config['model'], device="cpu", download_root=default_stt_path, local_files_only = True)
  except: #huggingface_hub.utils._errors.LocalEntryNotFoundError (but can't do that here since huggingfacehub not directly imported)
    c.log(f"Downloading Model: {central_config['model']}")
    model = WhisperModel(model_size_or_path=central_config['model'], device="cpu", download_root=default_stt_path)

  c.log(f"Loaded Model: {central_config['model']}")
elif central_config["mode"].startswith("remote"):
  c.log(f"Using remote STT services from the device \"{central_config['mode'].split(':')[1]}\"")

def transcribe(audio): 
  # TODO: Send audio to STT directly rather than using a file for it. Still record audio to /dev/shm for option to replay
  # TODO: Figure out why large models (distil and normal) cause this to significantly slow down, where any other model does it instantly
  # across significantly different tiers of hardware

  c.log("Transcribing...")

  raw_spoken_words = ""
  segments, info = model.transcribe(audio, beam_size=5, condition_on_previous_text=False) #condition_on_previous_text=False reduces hallucinations and inference time with no downsides for our short text
  for segment in segments:
    raw_spoken_words += segment.text
  c.log(f"Transcribed words: {raw_spoken_words}")

  return raw_spoken_words

def remote_transcribe(message_json: dict):
  remote_stt_device = central_config["mode"].split(":")[1]
  remote_stt_publish = f"bloob/{remote_stt_device}/cores/stt_util/transcribe"
  remote_stt_subscribe = f"bloob/{remote_stt_device}/cores/stt_util/finished"
  publish.single(remote_stt_publish, json.dumps(message_json), hostname=c.mqtt_host, port=c.mqtt_port, auth=c.mqtt_auth)

  # This section to make sure it ignores other potential requests being dealt with by the remote STT
  received_id = "?"
  while received_id != message_json["id"]:
    c.log(f"Waiting for response from \"{remote_stt_device}\"'s remote STT")
    received_remote_tts = json.loads(subscribe.simple(remote_stt_subscribe, hostname=c.mqtt_host, port=c.mqtt_port, auth=c.mqtt_auth).payload)
    received_id = received_remote_tts["id"]

  c.log(f"Transcribed words: {received_remote_tts['text']}")

  return received_remote_tts["text"]

def on_message(client, _, message):
  try:
    c.log("Waiting for input...")
    msg_json = json.loads(message.payload.decode())

    if central_config["mode"] == "local":
      with open(transcribed_audio_path,'wb+') as audio_file:
        #Encoding is like this because the string must first be encoded back into the base64 bytes format, then decoded again, this time as b64, into the original bytes.
        audio_file.write(base64.b64decode(msg_json["audio"].encode()))
      transcription = transcribe(str(transcribed_audio_path))
    elif central_config["mode"].startswith("remote"):
      transcription = remote_transcribe(msg_json)
  except KeyError:
    c.log("Couldn't find the correct keys in recieved JSON")
  c.log("Publishing output")
  stt_mqtt.publish(f"bloob/{arguments.device_id}/cores/stt_util/finished", json.dumps({"id": msg_json["id"], "text": transcription}), qos=1)

stt_mqtt = mqtt.Client()
stt_mqtt.connect(arguments.host, arguments.port)
stt_mqtt.on_message = on_message

stt_mqtt.subscribe(f"bloob/{arguments.device_id}/cores/stt_util/transcribe")


stt_mqtt.loop_forever()