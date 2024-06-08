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

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

arguments = pybloob.coreArgParse()


core_id = "greet"

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

publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, hostname=arguments.host, port=arguments.port)

for intent in intents:
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/intents/{intent['id']}", payload=json.dumps(intent), retain=True, hostname=arguments.host, port=arguments.port)

# Clears the published config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
def on_exit(*args):
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
  exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

while True:
  request_json = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/run", hostname=arguments.host, port=arguments.port).payload.decode())
  greeting = "Hello, World!"
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": request_json['id'], "text": greeting, "explanation": "The demo greeting core says " + greeting}), hostname=arguments.host, port=arguments.port)
