#!/bin/env python3
""" MQTT connected Intent Parser for Blueberry

Wishes to be provided with {"id": identifier_of_this_request: str, "text": text_to_parse: str}, over MQTT to "bloob/{arguments.device_id}/intent_parser/run"

Will respond with {"id": identifier_of_this_request: str, "intent": intent["intentName"]: str, "text": spoken_words, "core": intent["core"]: str} to "bloob/{arguments.device_id}/intent_parser/finished"
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
import paho.mqtt.publish as publish
import paho.mqtt.subscribe as subscribe

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")
arg_parser.add_argument('--identify', default="")

arguments = arg_parser.parse_args()

arguments.port = int(arguments.port)

core_id = "intent_parser"

if arguments.identify:
  print(json.dumps({"id": core_id}))
  exit()

# Can be provided with a str, or list, where it'll search for that str or 
# each str in the list as a whole word in spoken_words (or whatever the search_string arg is)
# and return them in spoken order
def getTextMatches(match_item, search_string):
  search_string = search_string.lower()

  # If we're given a list, we'll check for everything in that list, and return it in the order that it was spoken
  if type(match_item) is list:
    matches = [phrase for phrase in match_item if(phrase.lower() in search_string)]
    matches.sort(key=lambda phrase: search_string.find(phrase.lower()))
    return(matches)
  # If it's a string, check for it as a standalone word
  elif type(match_item) is str:
    # This converts the string into a list so that we only get whole word matches
    # Otherwise, "what's 8 times 12" would count as valid for checking the "time"
    # TODO: In the list section, check if phrases are only a single word, and use this logic
    # if so, otherwise use the current checking logic.
    if match_item in search_string.split(" "):
      return(match_item)
    else:
      return("")

# Can be provided with a list, which should contain objects with .names, 
# which is a list of potential different names for the device, where the first is
# the preferred name. It'll search for any of the names in spoken_words
# (or in the search_string arg if provided), and return those devices' objects in spoken order
def getDeviceMatches(match_item, search_string):

  search_string = search_string.lower()

  ## We want to return the actual device object, rather than just the text name of it.
  name_matches = []
  device_matches = []

  ## Firstly, we loop over the devices, get their names, and append the found names to a list (we cannot order the devices in this step
  ## since they would get ordered by their appearance in the main devices list, rather than in the spoken words)
  for device in devices:
    for name in device.names:
      if name.lower() in search_string:
        name_matches.append(name)

  ## Sort these names by their appearance in the spoken text
  name_matches.sort(key=lambda name: search_string.find(name.lower()))

  ## Go through each spoken device name in the order that it appears, find its matching device, and append it to a list.
  for name in name_matches:
    for device in devices:
      if name in device.names:
        device_matches.append(device)
        
  return(device_matches)

# Clean up inputs ########################################
def clean_input(text):

  cleaned_text = text.lstrip()

  # TODO: For x in list of words to replace, do this, to allow future additions
  cleaned_text = cleaned_text.replace("%", " percent")
  cleaned_text = cleaned_text.replace("&", " and")

  # Remove special characters from text, make lowercase
  cleaned_text = re.sub('[^A-Za-z0-9 ]+', "", cleaned_text).lower()
  return cleaned_text

# Intent Parsing ########################################
get_keyphrases = ["get", "what", "whats", "is"]
set_keyphrases = ["set", "make", "makes", "turn"]

state_bool_keyphrases = ["on", "off"]
state_brightness_keyphrases = ["brightness"]
state_percentage_keyphrases = ["percent", "%", "percentage"]

from datetime import datetime

intents = [

  {"intentName" : "getDate", "keywords": ["date", "day", "time"], "type": "get", "core": "date_handler", "private": True},
  {"intentName" : "setCar", "keywords": ["motor", "vehicle", "wheels"], "type": "set", "core": "date_handler", "private": True},
  {"intentName" : "getCat", "keywords": ["meow", "cat2", "cat"], "type": "get", "core": "cat_handler", "private": True},
  {"intentName" : "setColour", "keywords": ["yellow", "orange", "blue"], "type": "set", "core": "date_handler", "private": True}
  
]

def parse(text_to_parse, intents):
  if len(text_to_parse) == 0:
    return None, None
  
  for intent in intents:
    if intent.get("keywords") != None:
      if intent.get("type") == "set" and getTextMatches(match_item=set_keyphrases, search_string=text_to_parse):
        if getTextMatches(match_item=intent["keywords"], search_string=text_to_parse):
          return intent["intentName"], intent["core"]
          break
      elif intent.get("type") == "get" and getTextMatches(match_item=get_keyphrases, search_string=text_to_parse):
        if getTextMatches(match_item=intent["keywords"], search_string=text_to_parse):
          return intent["intentName"], intent["core"]
          break

  return None, None

while True:
  request_json = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/intent_parser/run").payload.decode())
  cleaned_input = clean_input(request_json["text"])
  parsed_intent, parsed_core = parse(text_to_parse=cleaned_input, intents=intents)
  publish.single(f"bloob/{arguments.device_id}/intent_parser/finished", payload=json.dumps({"intent": parsed_intent, "core": parsed_core, "text": cleaned_input, "id": request_json["id"]}), hostname=arguments.host, port=arguments.port)
  

# ## Get the time 
# elif getTextMatches("time"):
#   now = datetime.now()
#   if now.strftime('%p') == "PM":
#     apm = "PM"
#   else:
#     apm = "PM"
#   print(f"The time is {now.strftime('%I')}:{now.strftime('%M')} {apm}")
# ## Get the date
# elif getTextMatches("date"):
#   pass


# TODO: Special case words, check for the word at the start of speech, then send the rest on to whatever has asked for us to check for that case
# #Special case for "play" or "search" keywords for media and web queries:
# elif spoken_words_list[0] == "play":
#   pass
# elif spoken_words_list[0] == "search":
#   pass

