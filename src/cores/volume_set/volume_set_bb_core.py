#!/bin/env python3
""" Volume setter core for Blueberry
Core ID: volume_set

Follows the Bloob Core format for input / output

Sets the volume to - or increments it by - whatever percentage you say
"""
import argparse
import subprocess
import sys
import base64
import json
import pathlib
import signal

import random

import pybloob

core_dir = pathlib.Path(__file__).parents[0]

core_id = "volume_set"

arguments = pybloob.coreArgParse()
c = pybloob.coreMQTTInfo(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_auth=pybloob.pahoMqttAuthFromArgs(arguments))


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
    "numbers": {"any": "any"},
    "core_id": core_id
  },
  {
    "id" : "increment_volume",
    "keyphrases": [increase_words + decrease_words, ["volume", "loudness", "speaker", "speakers"]],
    "numbers": {"any": "any"},
    "core_id": core_id
  }
  
  ]

## Logging starts here
log_data = arguments.host, int(arguments.port), arguments.device_id, core_id
pybloob.log("Starting up...", log_data)

pybloob.publishConfig(core_config, c)

pybloob.publishIntents(intents, c)

## Get device configs from central config, instantiate
pybloob.log("Getting Centralised Config from Orchestrator", log_data)
central_config = pybloob.getCentralConfig(c)

if central_config == {}:
  min_bound = 0
  max_bound = 100
  audio_device = "Master"
  pybloob.log(f"No config found, assuming default audio device name ({audio_device}) and bounds ({min_bound}-{max_bound})", log_data)

else:
  min_bound = int(central_config["min_bound"])
  max_bound = int(central_config["max_bound"])
  audio_device = central_config["device_name"]
  pybloob.log(f"Config found, device name ({audio_device}) and bounds ({min_bound}-{max_bound})", log_data)

with open(core_dir.joinpath("volume_change.wav"), "rb") as audio_file:
	volume_change_audio = base64.b64encode(audio_file.read()).decode()

while True:
  pybloob.log("Waiting for input...", log_data)
  request_json = pybloob.waitForCoreCall(c)
  numbers = []
  for word in request_json["text"].split(" "):
    if word.isnumeric(): numbers.append(int(word))

  if len(numbers) == 1:
    percentage = int(min_bound+(numbers[0]*((max_bound-min_bound)/100)))

    if request_json["intent"] == "set_volume":
      pybloob.log(f"Setting volume to {percentage}%", log_data)
      subprocess.call(["amixer", "sset", audio_device, str(percentage) + "%"])

      to_speak = f"Setting the volume to {percentage} percent"
      explanation = f"Volume Set Core set the volume to {percentage}%"

    elif request_json["intent"] == "increment_volume":
      if pybloob.getTextMatches(increase_words, request_json["text"]):
        plus_minus = "+"
        increase_decrease = "Increasing"
      else:
        plus_minus = "-"
        increase_decrease = "Decreasing"

      to_speak = f"{increase_decrease} the volume by {percentage} percent"
      explanation = f"Volume Set Core is done {increase_decrease} the volume by {percentage}%"
      
      subprocess.call(["amixer", "sset", audio_device, str(percentage) + "%" + plus_minus])

    pybloob.playAudioFile(volume_change_audio, c)

  else:
    pybloob.log(f"Got {len(numbers)} instead of 1", log_data)
    to_speak = f"You didn't say 1 number to set the volume to, you said {len(numbers)}"
    explanation = f"Setting the volume failed, as the user said {len(numbers)} volume numbers instead of 1"

  pybloob.publishCoreOutput(request_json["id"], to_speak, explanation, c)