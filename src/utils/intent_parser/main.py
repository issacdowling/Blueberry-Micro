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


from bloob import getDeviceMatches, getTextMatches, log

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


log_data = arguments.host, int(arguments.port), arguments.device_id, core_id

# Clean up inputs ########################################
def clean_input(text):

  cleaned_text = text.lstrip()

  # TODO: For x in list of words to replace, do this, to allow future additions
  cleaned_text = cleaned_text.replace("%", " percent")
  cleaned_text = cleaned_text.replace("&", " and")

  # Remove special characters from text, make lowercase
  cleaned_text = re.sub('[^A-Za-z0-9 ]+', "", cleaned_text).lower()

  log(f"Cleaned original input - {text} - into - {cleaned_text}", log_data)

  return cleaned_text

# Intent Parsing ########################################
get_keyphrases = ["get", "what", "whats", "is"]
set_keyphrases = ["set", "make", "makes", "turn"]

state_bool_keyphrases = ["on", "off"]
state_brightness_keyphrases = ["brightness"]
state_percentage_keyphrases = ["percent", "%", "percentage"]

from datetime import datetime

log("Starting up...", log_data)

intents = []


# Get the list of cores, then get the config of each, find all intents, and load them here.
loaded_cores = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/list",hostname=arguments.host, port=arguments.port).payload.decode())["loaded_cores"]
for core_id in loaded_cores:
  log(f"Getting Config for {core_id}", log_data)
  core_conf = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/config",hostname=arguments.host, port=arguments.port).payload.decode())
  for intent in core_conf["intents"]:
    intents.append(intent)

log(f"Loaded Intents: {intents}", log_data)

loaded_collections = []
# Get the list of collections and load them here.
orchestrator_collections = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/collections/list",hostname=arguments.host, port=arguments.port).payload.decode())["loaded_collections"]
for collection_id in orchestrator_collections:
  log(f"Getting Collection: {collection_id}", log_data)
  collection = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/collections/{collection_id}",hostname=arguments.host, port=arguments.port).payload.decode())
  loaded_collections.append(collection)

log(f"Loaded Collections: {loaded_collections}", log_data)

def parse(text_to_parse, intents):
  if len(text_to_parse) == 0:
    log(f"0 length text inputted", log_data)
    return None, None
  
  ## TODO: Allow only checking for the first word
  ## TODO: ALlow checking for which wakeword was spoken
  intent_results = []

  # Explanation of this mess, for future generations
  # Each test is based on one key, such as "collections" or "keywords"
  # You should go through whatever internal logic is necessary to produce a yes or no for your test
  # But, in the end, you just return +1 vote if it succeeds, and nothing if it doesn't
  # I had many troubles with accidentally voting for each little internal test, such as for each keyword, etc
  # At the end, we compare the number of votes to the number of needed votes (determined by the number of those values - which are tests - were mentioned in the intent JSON)
  # If you have enough, you're added to the intent_results, where - in the future - we will have a way to deal with multiple intents
  # It would be useful, if you plan on adding to this, for you to explain the logic of your votes as you do it, like the collections test does (maybe show your internal test values)

  for intent in intents:
    intent_votes = 0
    needed_votes = 0

    # The number of tests needed to run is the number of votes needed to win, as each test votes once
    if intent.get("keywords"): needed_votes +=1
    if intent.get("collections"): needed_votes +=1

    if intent.get("keywords") != None and intent.get("keywords") != "" and intent.get("keywords") != []:
      keywords_pass = False
      failed_matches = False
      found_keywords = []

      for set_of_keywords in intent["keywords"]:
        if getTextMatches(match_item=set_of_keywords, check_string=text_to_parse): keywords_pass = True
        found_keywords.append(getTextMatches(match_item=set_of_keywords, check_string=text_to_parse))
      
      if intent.get("type") == "set" and not getTextMatches(match_item=set_keyphrases, check_string=text_to_parse):
        # Allows providing a single list of keywords to check, where at least one match is needed
        keywords_pass = False
          
      elif intent.get("type") == "get" and not getTextMatches(match_item=get_keyphrases, check_string=text_to_parse):
        keywords_pass = False

      if keywords_pass: intent_votes += 1

      log(f"{intent['intent_name']} - Keywords check votes: {keywords_pass}, {found_keywords} found", log_data)

    if intent.get("collections") != None and intent.get("collections") != [] and intent.get("collections") != [[]]:
      collection_votes = 0
      number_of_sets_of_collections = len(intent["collections"])
      for set_of_collections in intent["collections"]:
        something_in_this_set_has_passed = False
        for intent_collection_id in set_of_collections:
          for collection in loaded_collections:
            if intent_collection_id == collection["id"]:

              #Special case for any_number collection
              if intent_collection_id == "any_number":
                there_are_any_numbers = False
                for word in text_to_parse.split(" "):
                  if word.isnumeric(): there_are_any_numbers = True
                something_in_this_set_has_passed = True if there_are_any_numbers else False              
              
              # Any other special cases to be added as elifs here

              else:
                there_are_any_keywords = False
                for keyword in collection["keywords"]:
                  if keyword in text_to_parse:
                    something_in_this_set_has_passed = True
                    if collection.get("substitute") != None:
                      text_to_parse = text_to_parse.replace(keyword, collection["substitute"])

        if something_in_this_set_has_passed: collection_votes += 1

      if collection_votes == number_of_sets_of_collections:
        log(f"{intent['intent_name']} - Collections check votes: {True}, {collection_votes} of {number_of_sets_of_collections} needed collections passed", log_data)
        intent_votes += 1
      else:
        log(f"{intent['intent_name']} - Collections check votes: {False}, only {collection_votes} of {number_of_sets_of_collections} necessary collections passed", log_data)

      
    log(f"{intent_votes}/{needed_votes} votes for {intent['intent_name']}", log_data)
    if intent_votes > 0:
      intent_results.append(intent)

  log(f"Intent results length: {len(intent_results)}", log_data)
  if len(intent_results) == 1:
    return intent_results[0]["intent_name"], intent_results[0]["core_id"], text_to_parse
  if len(intent_results) == 0:
    return None, None, None

  return None, None, None

while True:
  log(f"Waiting for input...", log_data)
  request_json =  json.loads(subscribe.simple(f"bloob/{arguments.device_id}/intent_parser/run", hostname=arguments.host, port=arguments.port).payload.decode())
  cleaned_input = clean_input(request_json["text"])
  log(f"Received input, beginning parsing on text: {cleaned_input}", log_data)
  parsed_intent, parsed_core, text_out = parse(text_to_parse=cleaned_input, intents=intents)
  log(f"Outputting results, Core: {parsed_core}, Intent: {parsed_intent}", log_data)
  publish.single(f"bloob/{arguments.device_id}/intent_parser/finished", payload=json.dumps({"id": request_json["id"], "intent": parsed_intent, "core_id": parsed_core, "text": text_out}), hostname=arguments.host, port=arguments.port)