#!/bin/env python3
""" MQTT connected WLED core for Blueberry
Core ID: wled

Follows the Bloob Core format for input / output
"""
import argparse
import sys
import json
import pathlib
import signal

import requests

default_temp_path = pathlib.Path("/dev/shm/bloob")

bloobinfo_path = default_temp_path.joinpath("bloobinfo.txt")
with open(bloobinfo_path, "r") as bloobinfo_file:
  bloob_info = json.load(bloobinfo_file)

bloob_python_module_dir = pathlib.Path(bloob_info["install_path"]).joinpath("src").joinpath("python_module")
sys.path.append(str(bloob_python_module_dir))

from bloob import getDeviceMatches, getTextMatches, log, coreArgParse, pahoMqttAuthFromArgs, coreMQTTInfo, getCollection, getCentralConfig, publishIntents, publishConfig, waitForCoreCall, publishCoreOutput

arguments = coreArgParse()

core_id = "wled"

mqtt_auth = pahoMqttAuthFromArgs(arguments)
c = coreMQTTInfo(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_auth=mqtt_auth)

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

## Logging starts here
log_data = arguments.host, int(arguments.port), arguments.device_id, core_id
log("Starting up...", log_data)

wled_devices = []

## Get device configs from central config, instantiate
log("Getting Centralised Config from Orchestrator", log_data)
device_config = getCentralConfig(c)
if not device_config == {} and device_config.get("devices"):
  for device in device_config["devices"]:
    wled_devices.append(WledDevice(names=device["names"], ip_address=device["ip"]))

log("Getting colours Collection from Orchestrator", log_data)
## Get required "colours" Collection from central Collection list
colours_collection = getCollection(collection_name="colours", core_mqtt_info=c)

log("Getting boolean Collection from Orchestrator", log_data)
## Get required "boolean" Collection from central Collection list
boolean_collection = getCollection(collection_name="boolean", core_mqtt_info=c)

all_device_names = []
for device in wled_devices:
  for name in device.names:
    all_device_names.append(name)

state_keyphrases = boolean_collection["keyphrases"] + colours_collection["keyphrases"]

log(boolean_collection["keyphrases"], log_data)

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "WLED Device Handler",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/wled",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Allows setting / getting the basic states of WLED lights using their REST API",
    "version": "0.1",
    "license": "AGPLv3",
    "example_config": {
      "devices": [
        {
          "names": [
            "first device name",
            "other alias for device",
            "the first name is what will be used by bloob normally",
            "but you can say any of these and it'll work"
          ],
          "ip": "192.168.x.x"
        },
        {
          "names": [
            "I am a second device",
            "kitchen light"
          ],
          "ip": "172.30.x.x"
        }
      ]
    }
  }
}

intents = [
  {
  "id" : "setWLEDBoolOrColour",
  "keyphrases": [["$set"], all_device_names, ["$boolean", "$colours"]],
  "core_id": core_id
  },
  {
  "id" : "setWLEDBrightness",
  "keyphrases": [["$set"], all_device_names],
  "numbers": {"any": "any"},
  "core_id": core_id
  }
]

publishIntents(intents, c)

print(all_device_names)
log("Publishing Core Config", log_data)
publishConfig(core_config, c)

while True:
  log("Waiting for input...", log_data)
  request_json = waitForCoreCall(c)
  ## TODO: Actual stuff here, matching the right device from name, state, etc

  spoken_devices = getDeviceMatches(device_list=wled_devices, check_string=request_json["text"])
  spoken_states = getTextMatches(match_item=state_keyphrases, check_string=request_json["text"])

  # If there's a blank spot in the state, but there are numbers in the spoken words, do that.
  if not spoken_states:
    for word in request_json["text"].split(" "):
      if word.isnumeric():
        spoken_states.append(f"{word} percent")
  else:
    for index, state in enumerate(spoken_states):
      if not state:
        for word in request_json["text"].split(" "):
          if word.isnumeric():
            spoken_states[index] == f"{word} percent"

  log(f"Spoken devices: {spoken_devices}, spoken states: {spoken_states}", log_data)

  to_speak = ""
  explanation = ""
  for index, device in enumerate(spoken_devices):
    # This should mean that if only one state was spoken, it'll repeat for all mentioned devices
    try:
      spoken_state = spoken_states[index]

    except IndexError:
      pass
    ### Set the state ##################
    to_speak += (f"Turning the {device.friendly_name} {spoken_state}, " ) # Sample speech, will be better
    #Boolean
    if boolean_collection["variables"].get(spoken_state) == True:
      device.on()
    elif boolean_collection["variables"].get(spoken_state) == False:
      device.off()
    # Colours / custom states
    elif spoken_state in colours_collection["keyphrases"]:
      device.setColour(colours_collection["variables"][spoken_state])
    # Set percentage of device (normally brightness, but could be anything else)
    else:
      how_many_numbers = 0
      for word in request_json["text"].split(" "):
        if word.isnumeric():
          how_many_numbers += 1
          spoken_number = int(word)
      if how_many_numbers == 1:
        device.setPercentage(spoken_number)

  log(f"Publishing Output, {to_speak}", log_data)
  publishCoreOutput(request_json["id"], to_speak, explanation, c)


