#!/bin/env python3
""" Volume setter core for Blueberry
Core ID: volume_set

Follows the Bloob Core format for input / output

Sets the volume to - or increments it by - whatever percentage you say
"""
import argparse
import subprocess
import asyncio
import sys
import re
import base64
import json
import pathlib
import os
import signal

import random

default_temp_path = pathlib.Path("/dev/shm/bloob")

bloobinfo_path = default_temp_path.joinpath("bloobinfo.txt")
with open(bloobinfo_path, "r") as bloobinfo_file:
  bloob_info = json.load(bloobinfo_file)

bloob_python_module_dir = pathlib.Path(bloob_info["install_path"]).joinpath("src").joinpath("python_module")
sys.path.append(str(bloob_python_module_dir))

from bloob import getTextMatches, log

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

core_dir = pathlib.Path(__file__).parents[0]

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")

arguments = arg_parser.parse_args()

arguments.port = int(arguments.port)

core_id = "volume_set"

increase_words = ["up", "increase", "higher", "more"]
decrease_words = ["down", "decrease", "lower", "less", "decreeced"]

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Volume Setter",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/volume_set",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Sets (or increments) the volume",
    "version": 0.1,
    "license": "AGPLv3",
    "example_config": {
      "min_bound": 50,
      "max_bound": 90,
      "device_name": "Master"
    }
  }
}

intents = [{
    "id" : "set_volume",
    "keyphrases": [["$set"], ["volume", "loudness", "speaker", "speakers"]],
    #any_number
    "core_id": core_id
  },
  {
    "id" : "increment_volume",
    "keyphrases": [increase_words + decrease_words, ["volume", "loudness", "speaker", "speakers"]],
    #any_number
    "core_id": core_id
  }
  
  ]

## Logging starts here
log_data = arguments.host, int(arguments.port), arguments.device_id, core_id
log("Starting up...", log_data)

publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, hostname=arguments.host, port=arguments.port)

for intent in intents:
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/intents/{intent['id']}", payload=json.dumps(intent), retain=True, hostname=arguments.host, port=arguments.port)


# Clears the published config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
import signal
def on_exit(*args):
  log("Shutting Down...", log_data)
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
  exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

## Get device configs from central config, instantiate
log("Getting Centralised Config from Orchestrator", log_data)
central_config = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/central_config", hostname=arguments.host, port=arguments.port).payload.decode())

if central_config == None:
  min_bound = 0
  max_bound = 100
  audio_device = "Master"
  log(f"No config found, assuming default audio device name ({audio_device}) and bounds ({min_bound}-{max_bound})", log_data)

else:
  min_bound = int(central_config["min_bound"])
  max_bound = int(central_config["max_bound"])
  audio_device = central_config["device_name"]
  log(f"Config found, device name ({audio_device}) and bounds ({min_bound}-{max_bound})", log_data)

# Clears the published config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
def on_exit(*args):
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
  exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

with open(core_dir.joinpath("volume_change.wav"), "rb") as audio_file:
	volume_change_audio = base64.b64encode(audio_file.read()).decode()

while True:
  log("Waiting for input...", log_data)
  request_json = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/run", hostname=arguments.host, port=arguments.port).payload.decode())
  numbers = []
  for word in request_json["text"].split(" "):
    if word.isnumeric(): numbers.append(int(word))

  if len(numbers) == 1:
    percentage = int(min_bound+(numbers[0]*((max_bound-min_bound)/100)))

    if request_json["intent"] == "set_volume":
      log(f"Setting volume to {percentage}%", log_data)
      subprocess.call(["amixer", "sset", audio_device, str(percentage) + "%"])

      to_speak = f"Setting the volume to {percentage} percent"
      explanation = f"Volume Set Core set the volume to {percentage}%"

    elif request_json["intent"] == "increment_volume":
      if getTextMatches(increase_words, request_json["text"]):
        plus_minus = "+"
        increase_decrease = "Increasing"
      else:
        plus_minus = "-"
        increase_decrease = "Decreasing"

      to_speak = f"{increase_decrease} the volume by {percentage} percent"
      explanation = f"Volume Set Core is done {increase_decrease} the volume by {percentage}%"
      
      subprocess.call(["amixer", "sset", audio_device, str(percentage) + "%" + plus_minus])

    publish.single(topic=f"bloob/{arguments.device_id}/audio_playback/play_file", payload=json.dumps({"id": random.randint(1,1000), "audio": volume_change_audio}), hostname=arguments.host, port=arguments.port)

  else:
    log(f"Got {len(numbers)} instead of 1", log_data)
    to_speak = f"You didn't say 1 number to set the volume to, you said {len(numbers)}"
    explanation = f"Setting the volume failed, as the user said {len(numbers)} volume numbers instead of 1"

  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": request_json['id'], "text": to_speak, "explanation": explanation}), hostname=arguments.host, port=arguments.port)
