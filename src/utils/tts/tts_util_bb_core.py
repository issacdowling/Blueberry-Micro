#!/bin/env python3
""" MQTT connected TTS engine for Blueberry, making use of Piper TTS

Wishes to be provided with {"id": identifier_of_this_tts_request: str, "text": text_to_speak: str} over MQTT to "bloob/{arguments.device_id}/cores/tts_util/run"

Will respond with {"id": received_id: str, "audio": audio: str}, where audio is a WAV file, encoded as b64 bytes, then decoded into a string, to "bloob/{arguments.device_id}/cores/tts_util/finished"
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
from piper import download

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

default_temp_path = pathlib.Path("/dev/shm/bloob")
tts_temp_path = default_temp_path.joinpath("tts")

import pybloob

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 
default_tts_path = default_data_path.joinpath("tts")

if not os.path.exists(tts_temp_path):
  os.makedirs(tts_temp_path)

arguments = pybloob.coreArgParse()

core_id = "tts_util"

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

## Get device configs from central config, instantiate
pybloob.log("Getting Centralised Config from Orchestrator", log_data)
print(f"bloob/{arguments.device_id}/{core_id}/central_config")
central_config = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/central_config", hostname=arguments.host, port=arguments.port).payload.decode())

if not os.path.exists(default_tts_path):
  os.makedirs(default_tts_path)

tts_path = default_tts_path
tts_model_path = f"{tts_path}/{central_config['model']}.onnx"
output_audio_path = f"{tts_temp_path}/out.wav"

if not os.path.exists(tts_model_path):
	pybloob.log(f"Couldn't find voice ({central_config['model']}) locally, trying to download it.", log_data)
	try:
		download.ensure_voice_exists(central_config['model'], [tts_path], tts_path, download.get_voices(tts_path))
	except download.VoiceNotFoundError:
		pybloob.log(f"The requested voice ({central_config['model']}) was not found locally or able to be downloaded. The list of officially available Piper voices is {list(download.get_voices(tts_path, True).keys())}  Exiting.", log_data)
		exit()

def speak(text):
	speech_text = re.sub(r"^\W+|\W+$",'', text)
	pybloob.log(f"Inputted text - {text} - sanitised into - {speech_text}", log_data)
	pybloob.log(f"Generating speech", log_data)
	subprocess.call(f'echo "{speech_text}" | {sys.executable} -m piper --data-dir {tts_path} --download-dir {tts_path} --model {tts_model_path} --output_file {output_audio_path}', stdout=subprocess.PIPE, shell=True)
	pybloob.log(f"Spoken: {speech_text}", log_data)

async def connect():
	async with aiomqtt.Client(hostname=arguments.host, port=arguments.port) as client:
		pybloob.log(f"Waiting for input...", log_data)
		await client.subscribe(f"bloob/{arguments.device_id}/cores/tts_util/run")
		async for message in client.messages:
			try:
				message_payload = json.loads(message.payload.decode())
			except:
				pybloob.log("Error with payload.", log_data)

			if(message_payload.get('text') != None and message_payload.get('id') != None):
				speak(message_payload.get('text'))
				# encode speech to base64
				pybloob.log(f"Writing to temp file ({output_audio_path})", log_data)
				with open(output_audio_path, 'rb') as f:
					encoded = base64.b64encode(f.read())
					str_encoded = encoded.decode()
					pybloob.log(f"Publishing Output", log_data)
				await client.publish(f"bloob/{arguments.device_id}/cores/tts_util/finished", json.dumps({"id": message_payload.get('id'), "audio":str_encoded}), qos=1)


asyncio.run(connect())
