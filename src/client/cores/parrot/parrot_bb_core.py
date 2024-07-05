#!/bin/env python3
"""Parrot (speech repeater) core for Blueberry
Core ID: parrot

Follows the Bloob Core format for input / output

Repeats your speech
"""
import pathlib


import pybloob

core_dir = pathlib.Path(__file__).parents[0]

core_id = "parrot"

arguments = pybloob.coreArgParse()
c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"))

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

c.log("Starting up...")

c.publishConfig(core_config)

c.publishIntents(intents)

while True:
  c.log("Waiting for input")
  requestJson = c.waitForCoreCall()
  repeatText = requestJson["text"]
  for parrot_word in parrot_words:
    if repeatText.startswith(parrot_word):
      repeatText = repeatText[len(parrot_word):]
  c.log(f"Parroting: {repeatText}")
  c.publishCoreOutput(requestJson["id"], repeatText, f"The Parrot Core only wants you to output the following text, as the user asked for it to be repeated: {repeatText}")
