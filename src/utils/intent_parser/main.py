#!/bin/env python3
""" MQTT connected Intent Parser for Blueberry

Wishes to be provided with {"id": identifier_of_this_request: str, "text": text_to_parse: str}, over MQTT to "bloob/{arguments.device_id}/intent_parser/run"

Will respond with {"id": identifier_of_this_request: str, "intent": intent["intentName"]: str, "text": cleaned_up_text, "core": intent["core"]: str} to "bloob/{arguments.device_id}/intent_parser/finished"
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
import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

bloob_python_module_dir = pathlib.Path(__file__).parents[2].joinpath("python_module")
sys.path.append(str(bloob_python_module_dir))

from bloob import getDeviceMatches, getTextMatches

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
  print(json.dumps({"id": core_id, "roles": ["util"]}))
  exit()

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

intents = []
# Get the list of cores, then get the config of each, find all intents, and load them here.
loaded_cores = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/list",hostname=arguments.host, port=arguments.port).payload.decode())["loaded_cores"]
for core_id in loaded_cores:
  print(core_id)
  core_conf = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/config",hostname=arguments.host, port=arguments.port).payload.decode())
  print(core_conf)
  for intent in core_conf["intents"]:
    intents.append(intent)

collections = []
# Get the list of collections and load them here.
loaded_collections = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/collections/list",hostname=arguments.host, port=arguments.port).payload.decode())["loaded_collections"]
for collection_id in loaded_collections:
  print(collection_id)
  collection = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/collections/{collection_id}",hostname=arguments.host, port=arguments.port).payload.decode())
  print(collection)
  collections.append(collection)

def parse(text_to_parse, intents):
  if len(text_to_parse) == 0:
    return None, None
  
  ## TODO: Allow only checking for the first word
  ## TODO: ALlow checking for which wakeword was spoken
  intent_vote = []
  for intent in intents:

    if intent.get("keywords") != None and intent.get("keywords") != "" and intent.get("keywords") != []:

      if type(intent["keywords"][0]) == str:
        if getTextMatches(match_item=intent["keywords"], check_string=text_to_parse):
          if intent not in intent_vote: intent_vote.append(intent)
        else:
          if intent in intent_vote: intent_vote.remove(intent)
      # TODO: Allow specifying extra keywords within a keyword (I guess it becomes an object), so there can be these conditional things per-keywords too
      # Allows providing multiple lists of keywords to check, where there must be at least one match in each list
      elif type(intent["keywords"][0]) == list:
        failed_matches = False
        for set_of_keywords in intent["keywords"]:
          if not getTextMatches(match_item=set_of_keywords, check_string=text_to_parse): failed_matches = True
        if not failed_matches:
          if intent not in intent_vote: intent_vote.append(intent)
        else:
          if intent in intent_vote: intent_vote.remove(intent)

      if intent.get("type") == "set" and not getTextMatches(match_item=set_keyphrases, check_string=text_to_parse):
        # Allows providing a single list of keywords to check, where at least one match is needed
        if intent in intent_vote: intent_vote.remove(intent)
          
      elif intent.get("type") == "get" and not getTextMatches(match_item=get_keyphrases, check_string=text_to_parse):
        if intent in intent_vote: intent_vote.remove(intent)
      
    
    if intent.get("collections") != None:
      collection_valid = False
      for collection in collections:
        if collection["id"] in intent["collections"]:
          for keyword in collection["keywords"]:
            if keyword in text_to_parse:
              collection_valid = True
              if collection.get("substitute") != None:
                text_to_parse = text_to_parse.replace(keyword, collection["substitute"])        
      if collection_valid:
        if intent not in intent_vote: intent_vote.append(intent)
      else:
        if intent in intent_vote: intent_vote.remove(intent)


  print(intent_vote)
  if len(intent_vote) == 1:
    return intent_vote[0]["intent_name"], intent_vote[0]["core_id"], text_to_parse
  if len(intent_vote) == 0:
    return None, None, None

  return None, None, None

while True:
  request_json =  json.loads(subscribe.simple(f"bloob/{arguments.device_id}/intent_parser/run", hostname=arguments.host, port=arguments.port).payload.decode())
  cleaned_input = clean_input(request_json["text"])
  parsed_intent, parsed_core, text_out = parse(text_to_parse=cleaned_input, intents=intents)
  publish.single(f"bloob/{arguments.device_id}/intent_parser/finished", payload=json.dumps({"id": request_json["id"], "intent": parsed_intent, "core_id": parsed_core, "text": text_out}), hostname=arguments.host, port=arguments.port)