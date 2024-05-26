#!/bin/env python3
""" MQTT connected weather getter core for Blueberry
Core ID: weather

Follows the Bloob Core format for input / output

Requires centralised config with key "weather" and value of an object: {"location": [lat,long], "temperature_unit": "celsius"/"fahrenheit"}. It is recommended that your lat/long is
kept to 1dp of precision, as this should be reasonable for weather requests, while not being too specific
"""
import argparse
import subprocess
import asyncio
import sys
import re
import json
import base64
import pathlib
import os
import signal

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

import requests

default_temp_path = pathlib.Path("/dev/shm/bloob")

bloobinfo_path = default_temp_path.joinpath("bloobinfo.txt")
with open(bloobinfo_path, "r") as bloobinfo_file:
  bloob_info = json.load(bloobinfo_file)

bloob_python_module_dir = pathlib.Path(bloob_info["install_path"]).joinpath("src").joinpath("python_module")
sys.path.append(str(bloob_python_module_dir))

from bloob import getDeviceMatches, getTextMatches, log

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")

arguments = arg_parser.parse_args()

arguments.port = int(arguments.port)

core_id = "weather"

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Weather Getter",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/weather",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Gets the weather using Open Meteo",
    "version": 0.1,
    "license": "AGPLv3"
  },
  "intents": [{
    "intent_id" : "getWeather",
    "core_id": core_id,
    "keywords": [["weather", "hot", "cold", "temperature", "raining", "sun"]],
    "collections": [["get"]],
    "wakewords": ["weather"]
  }]
  
}

# Load weathercodes from the drive, which should be placed next to this .py file
script_path = os.path.abspath(os.path.dirname(__file__))
with open(f"{script_path}/weathercodes.json", "r") as weather_file:
  # File by Stellasphere, modified / shrunken to fit my needs
  wmo_codes = json.load(weather_file)

## Logging starts here
log_data = arguments.host, int(arguments.port), arguments.device_id, core_id
log("Starting up...", log_data)

publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, hostname=arguments.host, port=arguments.port)

## Get device configs from central config, instantiate
log("Getting Centralised Config from Orchestrator", log_data)
central_config = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/central_config", hostname=arguments.host, port=arguments.port).payload.decode())

# Clears the published config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
def on_exit(*args):
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
  exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

while True:
  request_json = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/run", hostname=arguments.host, port=arguments.port).payload.decode())
  if central_config == None or central_config.get("location") == None:
    log("No location set in config", log_data)
    to_speak = "I couldn't get the weather, as you don't have a location set up in your configuration file"
    explanation = "The Weather Core could not get the weather, as the user has not configured their location"
  else:
    if central_config.get("temperature_unit") == None:
      log("No temperature unit set, defaulting to Celsius", log_data)
      temperature_unit = "celsius"
    else:
      temperature_unit = central_config["temperature_unit"]
    latlong = central_config["location"]
    weather = requests.get(f'https://api.open-meteo.com/v1/forecast?latitude={latlong[0]}&longitude={latlong[1]}&current=temperature_2m,is_day,weathercode&temperature_unit={temperature_unit}').json()
    to_speak = f'Right now, its {weather["current"]["temperature_2m"]} degrees {temperature_unit} and {wmo_codes[str(weather["current"]["weathercode"])]["day"]["description"]}'
    explanation = f'The Weather Core got that the temperature is {weather["current"]["temperature_2m"]} degrees {temperature_unit} and the conditions are {wmo_codes[str(weather["current"]["weathercode"])]["day"]["description"]}'

  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": request_json['id'], "text": to_speak, "explanation": explanation}), hostname=arguments.host, port=arguments.port)


