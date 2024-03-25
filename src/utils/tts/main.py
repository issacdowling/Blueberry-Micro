#!/bin/env python3
""" MQTT connected TTS engine for Blueberry, making use of Piper TTS

Wishes to be provided with {"id": identifier_of_this_tts_request: str, "text": text_to_speak: str} over MQTT to "bloob/{arguments.device_id}/tts/run"

Will respond with {"id": received_id: str, "audio": audio: str}, where audio is a WAV file, encoded as b64 bytes, then decoded into a string, to "bloob/{arguments.device_id}/tts/finished"
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

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 
default_tts_path = default_data_path.joinpath("tts")

default_temp_path = pathlib.Path("/dev/shm/bloob")
tts_temp_path = default_temp_path.joinpath("tts")

if not os.path.exists(tts_temp_path):
  os.makedirs(tts_temp_path)

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")
arg_parser.add_argument('--tts-path', default=default_tts_path)
arg_parser.add_argument('--tts-model', default="en_US-lessac-high")
arg_parser.add_argument('--identify', default="")
arguments = arg_parser.parse_args()

arguments.port = int(arguments.port)

core_id = "tts"
if arguments.identify:
  print(json.dumps({"id": core_id}))
  exit()


output_audio_path = f"{tts_temp_path}/out.wav"

def speak(text):
	speech_text = re.sub(r"^\W+|\W+$",'', text)
	tts_path = arguments.tts_path
	tts_model_path = f"{tts_path}/{arguments.tts_model}.onnx"
	subprocess.call(f'echo "{speech_text}" | {sys.executable} -m piper --data-dir {tts_path} --download-dir {tts_path} --model {tts_model_path} --output_file {output_audio_path}', stdout=subprocess.PIPE, shell=True)
	print(f"Spoken: {speech_text}")

async def connect():
	async with aiomqtt.Client(hostname=arguments.host, port=arguments.port) as client:
		await client.subscribe(f"bloob/{arguments.device_id}/tts/run")
		async for message in client.messages:
			try:
				message_payload = json.loads(message.payload.decode())
				if(message_payload.get('text') != None and message_payload.get('id') != None):
					speak(message_payload.get('text'))
					# encode speech to base64
					with open(output_audio_path, 'rb') as f:
						encoded = base64.b64encode(f.read())
						str_encoded = encoded.decode()
					await client.publish(f"bloob/{arguments.device_id}/tts/finished", json.dumps({"id": message_payload.get('id'), "audio":str_encoded}))
			except:
				print("Error with payload.")

asyncio.run(connect())
