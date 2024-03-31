#!/bin/env python3
""" MQTT connected WLED core for Blueberry
Core ID: wled

Follows the Bloob Core format for input / output
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

import requests

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

bloob_python_module_dir = pathlib.Path(__file__).parents[2].joinpath("python_module")
sys.path.append(str(bloob_python_module_dir))

from bloob import getDeviceMatches, getTextMatches

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")
arg_parser.add_argument('--identify', default="")
arguments = arg_parser.parse_args()

arguments.port = int(arguments.port)

core_id = "wled"

if arguments.identify:
  print(json.dumps({"id": core_id, "roles": ["intent_handler"]}))
  exit()

class WledDevice:
  def __init__(self,names,ip_address):
    self.names = names
    self.friendly_name = names[0]
    self.ip_address = ip_address

  def on(self):
    requests.post(f"http://{self.ip_address}/win&T=1")

  def off(self):
    requests.post(f"http://{self.ip_address}/win&T=0")

  def setColour(self,rgb_list):
    requests.post(f"http://{self.ip_address}/win&R={rgb_list[0]}&G={rgb_list[1]}&B={rgb_list[2]}")

  # TODO: Change percentage based on the current limit
  def setPercentage(self,percentage):
    requests.post(f"http://{self.ip_address}/win&A={int(percentage*2.55)}")

  def get_state(self):
    wled_json_state = requests.get(f"http://{self.ip_address}/json").json()
    if wled_json_state["state"]["on"] == True:
      on_off = "on"
    else:
      on_off = "off"
    return on_off
    
    ## TODO: Return the whole state, and in a generic format. Right now, just returns whether on or off
    ## I'm thinking it could return a string which is to be spoken, as this would deal with not having to create
    ## a generic format that could support all states for all devices.

  def is_on(self):
    wled_json_state = requests.get(f"http://{self.ip_address}/json").json()
    if wled_json_state["state"]["on"] == True:
      return True
    else:
      return False

wled_devices = []

## Get device configs from central config, instantiate
device_config = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/central_config", hostname=arguments.host, port=arguments.port).payload.decode())
for device in device_config["devices"]:
  wled_devices.append(WledDevice(names=device["names"], ip_address=device["ip"]))

## Get required "colours" Collection from central Collection list
colours_collection = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/collections/colours", hostname=arguments.host, port=arguments.port).payload.decode())

all_device_names = []
for device in wled_devices:
  for name in device.names:
    all_device_names.append(name)

state_bool_keyphrases = ["on", "off"]
state_brightness_keyphrases = ["brightness"]
state_percentage_keyphrases = ["percent", "%", "percentage"]

state_keyphrases = state_bool_keyphrases + state_brightness_keyphrases + state_percentage_keyphrases + colours_collection["keywords"]

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Date / Time Getter",
    "link": None,
    "author": None,
    "icon": None,
    "description": None,
    "version": 0.1,
    "license": "AGPLv3"
  },
  "intents": [{
    "intent_name" : "setWLED",
    "keywords": [all_device_names, state_keyphrases],
    "type": "set",
    "core_id": core_id,
    "private": True
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
  ## TODO: Actual stuff here, matching the right device from name, state, etc

  spoken_devices = getDeviceMatches(device_list=wled_devices, check_string=request_json["text"])
  spoken_states = getTextMatches(match_item=state_keyphrases, check_string=request_json["text"])

  to_speak = ""
  explanation = ""
  for index, device in enumerate(spoken_devices):
    # This should mean that if only one state was spoken, it'll repeat for all mentioned devices
    try:
      spoken_state = spoken_states[index]
      print(spoken_devices)
    except IndexError:
      pass
    ### Set the state ##################
    to_speak += (f"Turning {device.friendly_name} {spoken_state}, " ) # Sample speech, will be better
    print(to_speak)
    #Boolean
    if spoken_state == "on":
      device.on()
    elif spoken_state == "off":
      device.off()
    # Colours / custom states
    elif spoken_state in colours_collection["keywords"]:
      device.setColour(colours_collection["variables"][spoken_state])
    # Set percentage of device (normally brightness, but could be anything else)
    elif spoken_state in state_percentage_keyphrases:
      how_many_numbers = 0
      for word in request_json["text"].split(" "):
        if word.isnumeric():
          how_many_numbers += 1
          spoken_number = int(word)
      if how_many_numbers == 1 and "percent" in request_json["text"].split(" "):
        device.setPercentage(spoken_number)

  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": request_json['id'], "text": to_speak, "explanation": explanation, "end_type": "finish"}), hostname=arguments.host, port=arguments.port)


