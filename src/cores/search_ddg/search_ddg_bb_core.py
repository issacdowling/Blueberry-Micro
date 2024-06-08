#!/bin/env python3
""" MQTT connected weather getter core for Blueberry
Core ID: weather

Follows the Bloob Core format for input / output

Requires centralised config with key "weather" and value of an object: {"location": [lat,long], "temperature_unit": "celsius"/"fahrenheit"}. It is recommended that your lat/long is
kept to 1dp of precision, as this should be reasonable for weather requests, while not being too specific
"""
import argparse
import sys
import json
import pathlib
import signal

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish


from duckduckgo_search import DDGS

import pybloob

arguments = pybloob.coreArgParse()

core_id = "search_ddg"

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Web Search (DuckDuckGo)",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/search_ddg",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Searches the web using DuckDuckGo.",
    "version": 0.1,
    "license": "AGPLv3"
  }
}

intents = [{
    "id" : "search_ddg",
    "core_id": core_id,
    "prefixes": ["search"]
  }]

## Logging starts here
log_data = arguments.host, int(arguments.port), arguments.device_id, core_id
pybloob.log("Starting up...", log_data)

publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, hostname=arguments.host, port=arguments.port)

for intent in intents:
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/intents/{intent['id']}", payload=json.dumps(intent), retain=True, hostname=arguments.host, port=arguments.port)


## Get device configs from central config, instantiate
pybloob.log("Getting Centralised Config from Orchestrator", log_data)
central_config = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/central_config", hostname=arguments.host, port=arguments.port).payload.decode())

# Clears the published config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
def on_exit(*args):
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
  exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

## TODO: Add (option?) sending a link to the search and results through ntfy for getting more info
while True:
  request_json = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/run", hostname=arguments.host, port=arguments.port).payload.decode())
  text_to_speak = DDGS().text(request_json["text"][1:], max_results=1)[0]["body"]
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": request_json['id'], "text": text_to_speak, "explanation": "A DuckDuckGo search returned: " + text_to_speak}), hostname=arguments.host, port=arguments.port)
