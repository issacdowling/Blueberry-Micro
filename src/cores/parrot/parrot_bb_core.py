#!/bin/env python3
"""Parrot (speech repeater) core for Blueberry
Core ID: parrot

Follows the Bloob Core format for input / output

Repeats your speech
"""
import argparse
import subprocess
import sys
import base64
import json
import pathlib
import signal
import signal

import random

import pybloob

core_dir = pathlib.Path(__file__).parents[0]

core_id = "greet"

arguments = pybloob.coreArgParse()
c = pybloob.coreMQTTInfo(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_auth=pybloob.pahoMqttAuthFromArgs(arguments))

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Parrot",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/parrot",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Parrots your speech",
    "version": 0.1,
    "license": "AGPLv3"
  }
}

parrot_words = ["parrot", "simon says", "repeat after me"]

intents = [{
    "id" : "parrotSpeech",
    "prefixes": parrot_words,
    "core_id": core_id
  }  
  ]

## Logging starts here
log_data = arguments.host, int(arguments.port), arguments.device_id, core_id
pybloob.log("Starting up...", log_data)

pybloob.publishConfig(core_config, c)

pybloob.publishIntents(intents, c)

while True:
  pybloob.log("Waiting for input", log_data)
  requestJson = pybloob.waitForCoreCall(c)
  repeatText = requestJson["text"]
  for parrot_word in parrot_words:
    if repeatText.startswith(parrot_word):
      repeatText = repeatText[len(parrot_word):]
  pybloob.log(f"Parroting: {repeatText}", log_data)
  pybloob.publishCoreOutput(requestJson["id"], repeatText, f"The Parrot Core only wants you to output the following text, as the user asked for it to be repeated: {repeatText}", c)
