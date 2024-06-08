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

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

core_dir = pathlib.Path(__file__).parents[0]

arguments = pybloob.coreArgParse()

core_id = "parrot"

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

publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, hostname=arguments.host, port=arguments.port)

for intent in intents:
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/intents/{intent['id']}", payload=json.dumps(intent), retain=True, hostname=arguments.host, port=arguments.port)


# Clears the published config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
import signal
def on_exit(*args):
  pybloob.log("Shutting Down...", log_data)
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
  exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

while True:
  pybloob.log("Waiting for input", log_data)
  requestJson = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/run", qos=1, hostname=arguments.host, port=arguments.port).payload)
  repeatText = requestJson["text"]
  for parrot_word in parrot_words:
    if repeatText.startswith(parrot_word):
      repeatText = repeatText[len(parrot_word):]
  pybloob.log(f"Parroting: {repeatText}", log_data)
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": requestJson["id"], "text": repeatText, "explanation": f"The Parrot Core only wants you to output the following text, as the user asked for it to be repeated: {repeatText}"}), retain=False, hostname=arguments.host, port=arguments.port)
  
