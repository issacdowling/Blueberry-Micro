#!/bin/env python3
""" Tasmota control core for Blueberry - Direct HTTP commands
Core ID: tasmota

Follows standard core protocol
"""
import argparse
import asyncio
import sys
import json
import pathlib
import signal

import requests
import aiomqtt
import paho, paho.mqtt, paho.mqtt.publish

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
arg_parser.add_argument('--pass', dest="password")
arg_parser.add_argument('--device-id', default="test")

arguments = arg_parser.parse_args()

state_bool_keyphrases = ["on", "off"]
state_brightness_keyphrases = ["brightness"]
state_percentage_keyphrases = ["percent", "%", "percentage"]

state_keyphrases = state_bool_keyphrases + state_brightness_keyphrases + state_percentage_keyphrases

core_id = "tasmota"

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

# Clears the published config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
import signal
def on_exit(*args):
  log("Shutting Down...", log_data)
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
  exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

# connect to the broker
async def main():
    async with aiomqtt.Client(hostname=arguments.host, port=int(arguments.port), username=arguments.user, password=arguments.password) as client:
        print("connected")

        # subscribe to the topics

        # core-specific configuration topic
        await client.subscribe(f"bloob/{arguments.device_id}/cores/{core_id}/central_config")

        # intent topic
        await client.subscribe(f"bloob/{arguments.device_id}/cores/{core_id}/run")

        # Publish config on startup
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
            }
        }

        intents = [
                {
                    "id": "controlTasmota",
                    "keyphrases": [["$set"], all_device_names, state_keyphrases],
                    "core_id": core_id
                }
            ]

        await client.publish(f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, qos=1)

        for intent in intents:
            await client.publish(f"bloob/{arguments.device_id}/cores/{core_id}/intents/{intent['id']}", payload=json.dumps(intent), retain=True, qos=1)

        

        
        # handle messages
        async for message in client.messages:

            await handle_message(message, client)

async def handle_message(message, client):
    global state_keyphrases
    if(message.topic.matches(f"bloob/{arguments.device_id}/cores/{core_id}/central_config")):
        device_config = json.loads(message.payload.decode())
        if device_config != None:
          print(f"Device config received: {device_config}")
          # add the devices
          if device_config.get("devices"):
            for device in device_config["devices"]:
                loaded_tasmota_devices.append(TasmotaDevice(names=device["names"], ip_address=device["ip"]))
        else:
          state_keyphrases = []

    if(message.topic.matches(f"bloob/{arguments.device_id}/cores/{core_id}/run")):

        payload_json = json.loads(message.payload.decode())

        spoken_devices = getDeviceMatches(device_list=loaded_tasmota_devices, check_string=payload_json["text"])
        spoken_states = getTextMatches(match_item=state_keyphrases, check_string=payload_json["text"])

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

            await client.publish(f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": payload_json["id"], "text": to_speak, "explanation": explanation}))




def on_exit(*args):
    auth = None
    if arguments.user != None:
        auth = {"username": arguments.user, "password": arguments.password}
    paho.mqtt.publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host,port=int(arguments.port), auth=auth)
    exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

if __name__ == "__main__":
    asyncio.run(main())
