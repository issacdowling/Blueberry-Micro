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
  print(json.dumps({"id": core_id}))
  exit()

# Can be provided with a list, which should contain objects with .names, 
# which is a list of potential different names for the device, where the first is
# the preferred name. It'll search for any of the names in spoken_words
# (or in the search_string arg if provided), and return those devices' objects in spoken order
def getDeviceMatches(device_list, search_string):
  search_string = search_string.lower()

  ## We want to return the actual device object, rather than just the text name of it.
  name_matches = []
  device_matches = []

  ## Firstly, we loop over the devices, get their names, and append the found names to a list (we cannot order the devices in this step
  ## since they would get ordered by their appearance in the main devices list, rather than in the spoken words)
  for device in device_list:
    for name in device.names:
      if name.lower() in search_string:
        name_matches.append(name)

  ## Sort these names by their appearance in the spoken text
  name_matches.sort(key=lambda name: search_string.find(name.lower()))

  ## Go through each spoken device name in the order that it appears, find its matching device, and append it to a list.
  for name in name_matches:
    for device in device_list:
      if name in device.names:
        device_matches.append(device)
        
  return(device_matches)

### Define function for checking matches between a string and lists, then ordering them
def getSpeechMatches(match_item, check_string):
  if type(match_item) is list:
    matches = [phrase for phrase in match_item if(phrase in check_string)]
    matches.sort(key=lambda phrase: check_string.find(phrase))
    return(matches)
  elif type(match_item) is str:
    # This converts the string into a list so that we only get whole word matches
    # Otherwise, "what's 8 times 12" would count as valid for checking the "time"
    # TODO: In the list section, check if phrases are only a single word, and use this logic
    # if so, otherwise use the current checking logic.
    if match_item in check_string.split(" "):
      return(match_item)
    else:
      return("")

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

all_device_names = []
for device in wled_devices:
  for name in device.names:
    all_device_names.append(name)

state_bool_keyphrases = ["on", "off"]
state_brightness_keyphrases = ["brightness"]
state_percentage_keyphrases = ["percent", "%", "percentage"]

state_keyphrases = state_bool_keyphrases + state_brightness_keyphrases + state_percentage_keyphrases

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

  spoken_devices = getDeviceMatches(device_list=wled_devices, search_string=request_json["text"])
  spoken_states = getSpeechMatches(match_item=state_keyphrases, check_string=request_json["text"])

  to_speak = ""
  explanation = ""
  for index, device in enumerate(spoken_devices):
    # This should mean that if only one state was spoken, it'll repeat for all mentioned devices
    try:
      spoken_state = spoken_states[index]
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
    # elif spoken_state in state_colour_keyphrases:
    #   device.setColour(colours_json["rgb"][spoken_state])
    # Set percentage of device (normally brightness, but could be anything else)
    elif spoken_state in state_percentage_keyphrases:
      how_many_numbers = 0
      for word in request_json["text"].split(" "):
        if word.isnumeric():
          how_many_numbers += 1
          spoken_number = int(word)
      if how_many_numbers == 1 and "percent" in request_json["text"].split(" "):
        device.setPercentage(spoken_number)

  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": request_json['id'], "speech": to_speak, "explanation": explanation, "end_type": "finish"}), hostname=arguments.host, port=arguments.port)


