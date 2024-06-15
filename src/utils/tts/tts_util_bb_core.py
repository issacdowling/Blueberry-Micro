#!/bin/env python3
""" MQTT connected TTS engine for Blueberry, making use of Piper TTS

Wishes to be provided with {"id": identifier_of_this_tts_request: str, "text": text_to_speak: str} over MQTT to "bloob/{arguments.device_id}/cores/tts_util/run"

Will respond with {"id": received_id: str, "audio": audio: str}, where audio is a WAV file, encoded as b64 bytes, then decoded into a string, to "bloob/{arguments.device_id}/cores/tts_util/finished"
"""
import subprocess
import asyncio
import aiomqtt
import sys
import re
import json
import base64
import pathlib
import os

from piper import download, PiperVoice
import wave

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

default_temp_path = pathlib.Path("/dev/shm/bloob")
tts_temp_path = default_temp_path.joinpath("tts")

import pybloob

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 
default_tts_path = default_data_path.joinpath("tts")

if not os.path.exists(tts_temp_path):
  os.makedirs(tts_temp_path)

core_id = "tts_util"

arguments = pybloob.coreArgParse()
c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"))

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

c.publishConfig(core_config)

c.log("Starting up...")

## Get device configs from central config, instantiate
c.log("Getting Centralised Config from Orchestrator")
print(f"bloob/{arguments.device_id}/{core_id}/central_config")
central_config = c.getCentralConfig()

if not os.path.exists(default_tts_path):
  os.makedirs(default_tts_path)

tts_path = default_tts_path
tts_model_path = f"{tts_path}/{central_config['model']}.onnx"
output_audio_path = f"{tts_temp_path}/out.wav"

voice = PiperVoice.load(tts_model_path)

if not os.path.exists(tts_model_path):
	c.log(f"Couldn't find voice ({central_config['model']}) locally, trying to download it.")
	try:
		download.ensure_voice_exists(central_config['model'], [tts_path], tts_path, download.get_voices(tts_path))
	except download.VoiceNotFoundError:
		c.log(f"The requested voice ({central_config['model']}) was not found locally or able to be downloaded. The list of officially available Piper voices is {list(download.get_voices(tts_path, True).keys())}  Exiting.")
		exit()

def speak(text):
	speech_text = re.sub(r"^\W+|\W+$",'', text)
	c.log(f"Inputted text - {text} - sanitised into - {speech_text}. Generating speech.")

	with wave.open(output_audio_path, 'wb') as speech_wav:
		speech_wav.setsampwidth(2) # 2 bytes, 16-bit audio
		speech_wav.setnchannels(1)

		speech_wav.setframerate(voice.config.sample_rate)

		for frame in voice.synthesize_stream_raw(speech_text):
			speech_wav.writeframes(frame)

	c.log(f"Spoken: {speech_text}")

async def connect():
	async with aiomqtt.Client(hostname=arguments.host, port=arguments.port) as client:
		c.log(f"Waiting for input...")
		await client.subscribe(f"bloob/{arguments.device_id}/cores/tts_util/run")
		async for message in client.messages:
			try:
				message_payload = json.loads(message.payload.decode())
			except:
				c.log("Error with payload.")

			if(message_payload.get('text') != None and message_payload.get('id') != None):
				speak(message_payload.get('text'))
				# encode speech to base64
				c.log(f"Writing to temp file ({output_audio_path})")
				with open(output_audio_path, 'rb') as f:
					encoded = base64.b64encode(f.read())
					str_encoded = encoded.decode()
					c.log(f"Publishing Output")
				await client.publish(f"bloob/{arguments.device_id}/cores/tts_util/finished", json.dumps({"id": message_payload.get('id'), "audio":str_encoded}), qos=1)


asyncio.run(connect())
