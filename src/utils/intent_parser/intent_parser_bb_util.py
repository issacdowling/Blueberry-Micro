#!/bin/env python3
""" MQTT connected Intent Parser for Blueberry

Wishes to be provided with {"id": identifier_of_this_request: str, "text": text_to_parse: str}, over MQTT to "bloob/{arguments.device_id}/intent_parser/run"

Will respond with {"id": identifier_of_this_request: str, "intent": intent["intentName"]: str, "text": cleaned_up_text, "core_id": intent["core"]: str} to "bloob/{arguments.device_id}/intent_parser/finished"
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

default_temp_path = pathlib.Path("/dev/shm/bloob")

bloobinfo_path = default_temp_path.joinpath("bloobinfo.txt")
with open(bloobinfo_path, "r") as bloobinfo_file:
  bloob_info = json.load(bloobinfo_file)

bloob_python_module_dir = pathlib.Path(bloob_info["install_path"]).joinpath("src").joinpath("python_module")
sys.path.append(str(bloob_python_module_dir))

from bloob import getDeviceMatches, getTextMatches, log

default_data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob") 

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")


arguments = arg_parser.parse_args()

arguments.port = int(arguments.port)

core_id = "intent_parser"

log_data = arguments.host, int(arguments.port), arguments.device_id, core_id

# Clean up inputs ########################################
def clean_input(text):

  cleaned_text = text.lstrip()

  # TODO: For x in list of words to replace, do this, to allow future additions
  cleaned_text = cleaned_text.replace("%", " percent")

  cleaned_text = cleaned_text.replace("&", " and")

  cleaned_text = cleaned_text.replace("+", " plus")
  cleaned_text = cleaned_text.replace("*", " times")
  cleaned_text = cleaned_text.replace("-", " minus")
  cleaned_text = cleaned_text.replace("/", " over")

  # Remove special characters from text, make lowercase
  cleaned_text = re.sub('[^A-Za-z0-9 ]+', "", cleaned_text).lower()

  log(f"Cleaned original input - {text} - into - {cleaned_text}", log_data)

  return cleaned_text

# Intent Parsing ########################################
from datetime import datetime

log("Starting up...", log_data)

intents = []


# Get the list of cores, then get the config of each, find all intents, and load them here.
loaded_cores = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/list",hostname=arguments.host, port=arguments.port).payload.decode())["loaded_cores"]
for core_id in loaded_cores:
  log(f"Getting Config for {core_id}", log_data)
  core_conf = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/config",hostname=arguments.host, port=arguments.port).payload.decode())
  if core_conf.get("intents"):
    for intent in core_conf["intents"]:
      intents.append(intent)

# Get the list of Instant Intents
instant_intent_words = []
for intent in intents:
  if intent.get("wakewords"):
    for wakeword in intent["wakewords"]:
      instant_intent_words.append(wakeword)

log(f"Loaded Intents: {intents}", log_data)

loaded_collections = []
# Get the list of collections and load them here.
orchestrator_collections = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/collections/list",hostname=arguments.host, port=arguments.port).payload.decode())["loaded_collections"]
for collection_id in orchestrator_collections:
  log(f"Getting Collection: {collection_id}", log_data)
  collection = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/collections/{collection_id}",hostname=arguments.host, port=arguments.port).payload.decode())
  loaded_collections.append(collection)

log(f"Loaded Collections: {loaded_collections}", log_data)

def parse(uncleaned_text_to_parse, intents):
  if len(uncleaned_text_to_parse) == 0:
    log(f"0 length text inputted", log_data)
    return None, None, None
  
  ## TODO: Allow only checking for the first word
  ## TODO: ALlow checking for which wakeword was spoken
  intent_results = []

  text_to_parse = clean_input(uncleaned_text_to_parse)
  log(f"Received input, beginning parsing on text: {text_to_parse}", log_data)

  # Explanation of this mess, for future generations
  # Each test is based on one key, such as "collections" or "keywords"
  # You should go through whatever internal logic is necessary to produce a yes or no for your test
  # But, in the end, you just return +1 vote if it succeeds, and nothing if it doesn't
  # I had many troubles with accidentally voting for each little internal test, such as for each keyword, etc
  # At the end, we compare the number of votes to the number of needed votes (determined by the number of those values - which are tests - were mentioned in the intent JSON)
  # If you have enough, you're added to the intent_results, where - in the future - we will have a way to deal with multiple intents
  # It would be useful, if you plan on adding to this, for you to explain the logic of your votes as you do it, like the collections test does (maybe show your internal test values)

  for intent in intents:
    #Check if the text exactly matches the name of an Instant Intent word
    if intent.get("wakewords") != None:
      for wakeword in intent["wakewords"]:
        # Specifically use the UNCLEANED text_to_parse, so that special characters are preserved
        if wakeword == uncleaned_text_to_parse and wakeword in intent.get("wakewords"):
          return intent["intent_id"], intent["core_id"], uncleaned_text_to_parse


    intent_votes = 0
    needed_votes = 0

    # The number of tests needed to run is the number of votes needed to win, as each test votes once
    if intent.get("keywords"): needed_votes +=1
    if intent.get("collections"): needed_votes +=1
    if intent.get("prefixes"): needed_votes +=1
    if intent.get("suffixes"): needed_votes +=1

    if intent.get("keywords") != None and intent.get("keywords") != "" and intent.get("keywords") != []:
      keywords_votes = 0
      number_of_sets_of_keywords = len(intent["keywords"])
      found_keywords = []

      for set_of_keywords in intent["keywords"]:
        something_in_this_set_has_passed = False
        # If a "keyword" is a single word - as opposed to a phrase - only match the whole word,
        # else accept non-whole matches since it's unlikely that a whole phrase would accidentally be inside another
        # Came from issues where "time" would conflict with "times" in different cores
        whole_words_only = True
        for keyword in set_of_keywords:
          if not len(keyword.split(" ")) == 1:
            whole_words_only = False
          match = getTextMatches(match_item=keyword, check_string=text_to_parse, whole_words_only=whole_words_only)
          if match: 
            something_in_this_set_has_passed = True
            found_keywords.append(match)
        if something_in_this_set_has_passed:
          keywords_votes += 1

      if keywords_votes == number_of_sets_of_keywords: intent_votes += 1

      log(f"{intent['intent_id']} - Keywords check votes: {keywords_votes}/{number_of_sets_of_keywords}, {found_keywords} found", log_data)

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
                if there_are_any_numbers: something_in_this_set_has_passed = True
              
              # Any other special cases to be added as elifs here

              else:
                # Go through each keyword in the collection. If the keyword is one word, it must be a whole word match
                # If it is a multi-word phrase, we are ok without it being a whole word match, so things work either way
                there_are_any_keywords = False
                for keyword in collection["keywords"]:

                  whole_words_only = True
                  if not len(keyword.split(" ")) == 1:
                    whole_words_only = False

                  if getTextMatches(match_item=keyword, check_string=text_to_parse, whole_words_only=whole_words_only):
                    something_in_this_set_has_passed = True
                    if collection.get("substitute") != None:
                      text_to_parse = text_to_parse.replace(keyword, collection["substitute"])

        if something_in_this_set_has_passed: collection_votes += 1

      if collection_votes == number_of_sets_of_collections:
        log(f"{intent['intent_id']} - Collections check votes: {True}, {collection_votes} of {number_of_sets_of_collections} needed collections passed", log_data)
        intent_votes += 1
      else:
        log(f"{intent['intent_id']} - Collections check votes: {False}, only {collection_votes} of {number_of_sets_of_collections} necessary collections passed", log_data)


    if intent.get("prefixes") != None and intent.get("prefixes") != []:
      was_prefix_found = False
      for prefix in intent["prefixes"]:
        if text_to_parse.startswith(prefix):
          was_prefix_found = True
          which_prefix_found = prefix
      
      if was_prefix_found:
        intent_votes += 1
        log(f"{intent['intent_id']} - Prefix check vote passed: [{which_prefix_found}] found at the start of speech.", log_data)
      else:
        log(f"{intent['intent_id']} - Prefix check vote failed.", log_data)


    if intent.get("suffixes") != None and intent.get("suffixes") != []:
      was_suffix_found = False
      for suffix in intent["suffixes"]:
        if text_to_parse.endswith(suffix):
          was_suffix_found = True
          which_suffix_found = suffix
      
      if was_suffix_found:
        intent_votes += 1
        log(f"{intent['intent_id']} - Suffix check vote passed: [{which_suffix_found}] found at the end of speech.", log_data)
      else:
        log(f"{intent['intent_id']} - Suffix check vote failed.", log_data)


    log(f"{intent_votes}/{needed_votes} votes for {intent['intent_id']}", log_data)
    if intent_votes == needed_votes:
      intent_results.append(intent)

  log(f"Intent results length: {len(intent_results)}", log_data)
  if len(intent_results) == 1:
    return intent_results[0]["intent_id"], intent_results[0]["core_id"], text_to_parse
  if len(intent_results) == 0:
    return None, None, None

  return None, None, None

while True:
  log(f"Waiting for input...", log_data)
  request_json =  json.loads(subscribe.simple(f"bloob/{arguments.device_id}/intent_parser/run", hostname=arguments.host, port=arguments.port).payload.decode())
  parsed_intent, parsed_core, text_out = parse(uncleaned_text_to_parse=request_json["text"], intents=intents)
  log(f"Outputting results, Core: {parsed_core}, Intent: {parsed_intent}", log_data)
  publish.single(f"bloob/{arguments.device_id}/intent_parser/finished", payload=json.dumps({"id": request_json["id"], "intent": parsed_intent, "core_id": parsed_core, "text": text_out}), hostname=arguments.host, port=arguments.port)