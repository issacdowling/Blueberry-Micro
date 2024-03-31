#!/bin/env python3
""" Tasmota control core for Blueberry - Direct HTTP commands
Core ID: tasmota

Follows standard core protocol
"""
import argparse
import asyncio
import sys
import re
import json
import base64
import pathlib
import os
import signal

import requests
import aiomqtt
import paho, paho.mqtt, paho.mqtt.publish
#import paho.mqtt.publish

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass', dest="password")
arg_parser.add_argument('--device-id', default="test")
arg_parser.add_argument('--identify', default="")
arguments = arg_parser.parse_args()

state_bool_keyphrases = ["on", "off"]
state_brightness_keyphrases = ["brightness"]
state_percentage_keyphrases = ["percent", "%", "percentage"]

state_keyphrases = state_bool_keyphrases + state_brightness_keyphrases + state_percentage_keyphrases

core_id = "tasmota"


if arguments.identify:
    print(json.dumps({"id": core_id}))
    exit()

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

all_device_names = []
class TasmotaDevice:
    def __init__(self, names, ip_address):
        self.names = names
        self.friendly_name = names[0]
        self.ip_address = ip_address
        self.request_uri = f"http://{self.ip_address}"
        if(self.ip_address.endswith("/cm")):
          self.request_uri += "?"
        else:
          self.request_uri += "&"

        for name in self.names:
            all_device_names.append(name)

    def on(self):
      requests.get(f"{self.request_uri}cmnd=Power%201")
    def off(self):
      requests.get(f"{self.request_uri}cmnd=Power%200")
    def is_on(self):
        return NotImplementedError

loaded_tasmota_devices = []

# connect to the broker
async def main():
    async with aiomqtt.Client(hostname=arguments.host, port=arguments.port, username=arguments.user, password=arguments.password) as client:
        print("connected")

        # subscribe to the topics

        # core-specific configuration topic
        await client.subscribe(f"bloob/{arguments.device_id}/cores/{core_id}/central_config")

        # intent topic
        await client.subscribe(f"bloob/{arguments.device_id}/cores/{core_id}/run")
        
        # handle messages
        async for message in client.messages:

            await handle_message(message, client)

async def handle_message(message, client):

    if(message.topic.matches(f"bloob/{arguments.device_id}/cores/{core_id}/central_config")):
        device_config = json.loads(message.payload.decode())
        print(f"Device config received: {device_config}")
        # add the devices
        for device in device_config["devices"]:
            loaded_tasmota_devices.append(TasmotaDevice(names=device["names"], ip_address=device["ip"]))
        core_config = {
            "metadata": {
                "core_id": core_id,
                "friendly_name": "Tasmota device control",
                "link": None,
                "author": None,
                "icon": None,
                "description": None,
                "version": 1.0,
                "license": "AGPLv3"
            },
            "intents": [
                {
                    "intent_name": "controlTasmota",
                    "keywords": [all_device_names, state_keyphrases],
                    "type": "set",
                    "core_id": core_id,
                    "private": True
                }
            ]
        }
        # send out startup messages

        await client.publish(f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, qos=1)
    if(message.topic.matches(f"bloob/{arguments.device_id}/cores/{core_id}/run")):

        payload_json = json.loads(message.payload.decode())

        spoken_devices = getDeviceMatches(device_list=loaded_tasmota_devices, search_string=payload_json["text"])
        spoken_states = getSpeechMatches(match_item=state_keyphrases, check_string=payload_json["text"])

        to_speak = ""
        explanation = ""
        for index,device in enumerate(spoken_devices):
            try:
                spoken_state = spoken_states[index]
            except IndexError:
                pass
            to_speak += f"Turning {device.friendly_name} {spoken_state}, "
            print(to_speak)
            if(spoken_state == "on"):
                device.on()
            elif spoken_state == ("off"):
                device.off()

            await client.publish(f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": payload_json["id"], "speech": to_speak, "explanation": explanation, "end_type": "finish"}))




def on_exit(*args):
    auth = None
    if arguments.user != None:
        auth = {"username": arguments.user, "password": arguments.password}
    paho.mqtt.publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host,port=arguments.port, auth=auth)
    exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

if __name__ == "__main__":
    asyncio.run(main())
