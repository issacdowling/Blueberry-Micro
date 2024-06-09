#!/bin/env python3
""" Basic greeter core for Blueberry
Core ID: greet_demo

Says hi back to you.
"""
import argparse
import sys
import json
import pathlib
import signal

import pybloob

core_id = "greet"

arguments = pybloob.coreArgParse()
c = pybloob.coreMQTTInfo(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_auth=pybloob.pahoMqttAuthFromArgs(arguments))

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Greeting Demo",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/greet_demo",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Says hi back to you",
    "version": 0.1,
    "license": "AGPLv3"
  }
}

intents = [{
    "id" : "helloGreet",
    "keyphrases": [["hello", "hi"]],
    "core_id": core_id
  }]

pybloob.publishConfig(core_config, c)

pybloob.publishIntents(intents, c)

while True:
  request_json = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/run", hostname=arguments.host, port=arguments.port).payload.decode())
  greeting = "Hello, World!"
  pybloob.publishCoreOutput(request_json["id"], greeting, f"The Greeting Core says {greeting}", c)
