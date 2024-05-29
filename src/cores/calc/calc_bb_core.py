#!/bin/env python3
""" MQTT connected date / time getter core for Blueberry
Core ID: date_time_get

Follows the Bloob Core format for input / output

Returns the date if your query includes date, time if your query includes the time, and both if it includes both / neither.
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

default_temp_path = pathlib.Path("/dev/shm/bloob")

bloobinfo_path = default_temp_path.joinpath("bloobinfo.txt")
with open(bloobinfo_path, "r") as bloobinfo_file:
  bloob_info = json.load(bloobinfo_file)

bloob_python_module_dir = pathlib.Path(bloob_info["install_path"]).joinpath("src").joinpath("python_module")
sys.path.append(str(bloob_python_module_dir))

from bloob import getTextMatches, log

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")
arguments = arg_parser.parse_args()

arguments.port = int(arguments.port)

core_id = "calc"

add_words = ["add", "plus"]
minus_words = ["minus", "take"]
multiply_words = ["times", "multiplied"]
divide_words = ["over", "divide"]

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Very Basic Calculator",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/calc",
    "author": "Issac Dowling",
    "icon": None,
    "description": "A very very simple calculator Core",
    "version": 0.1,
    "license": "AGPLv3"
  },
  "intents": [{
    "id" : "calc",
    "keyphrases": [add_words + minus_words + multiply_words + divide_words],
    "collections": [["get"], ["any_number"]],
    "core_id": core_id
  }]
}

publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, hostname=arguments.host, port=arguments.port)

# Clears the published config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
def on_exit(*args):
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
  exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

while True:
  request_json = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/run", hostname=arguments.host, port=arguments.port).payload.decode())
  numbers = []
  for word in request_json["text"].split(" "):
    if word.isnumeric(): numbers.append(int(word))

  if len(numbers) == 2:
    if getTextMatches(match_item=add_words, check_string=request_json["text"]):
      operator = " plus "
      result = numbers[0] + numbers[1]
    elif getTextMatches(match_item=minus_words, check_string=request_json["text"]):
      operator = " minus "
      result = numbers[0] - numbers[1]
    elif getTextMatches(match_item=divide_words, check_string=request_json["text"]):
      operator = " divided by "
      result = numbers[0] / numbers[1]
    elif getTextMatches(match_item=multiply_words, check_string=request_json["text"]):
      operator = " multiplied by "
      result = numbers[0] * numbers[1]

    to_speak = f'{numbers[0]} {operator} {numbers[1]} equals {str(result).replace(".", " point ")}'
    explanation = f'Calculator Core got that {numbers[0]} {operator} {numbers[1]} equals {str(result).replace(".", " point ")}'

  else:
    to_speak = f"You didn't say 2 numbers, you said {len(numbers)}"
    explanation = f"Calculator failed, as the user didn't say the 2 required numbers, they said {len(numbers)}"

  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": request_json['id'], "text": to_speak, "explanation": explanation}), hostname=arguments.host, port=arguments.port)
