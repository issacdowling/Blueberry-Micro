import paho.mqtt.publish as publish
import paho.mqtt.subscribe as subscribe
import json
import random

bloobQOS = 1

# Can be provided with a list, which should contain objects with .names, 
# which is a list of potential different names for the device, where the first is
# the preferred name. It'll search for any of the names in spoken_words
# (or in the check_string arg if provided), and return those devices' objects in spoken order
def getDeviceMatches(device_list, check_string):
  check_string = check_string.lower()

  ## We want to return the actual device object, rather than just the text name of it.
  name_matches = []
  device_matches = []

  ## Firstly, we loop over the devices, get their names, and append the found names to a list (we cannot order the devices in this step
  ## since they would get ordered by their appearance in the main devices list, rather than in the spoken words)
  for device in device_list:
    for name in device.names:
      if name.lower() in check_string:
        name_matches.append(name)

  ## Sort these names by their appearance in the spoken text
  name_matches.sort(key=lambda name: check_string.find(name.lower()))

  ## Go through each spoken device name in the order that it appears, find its matching device, and append it to a list.
  for name in name_matches:
    for device in device_list:
      if name in device.names:
        device_matches.append(device)
        
  return(device_matches)

# Can be provided with a str, or list, where it'll search for that str or 
# each str in the list as a whole word in spoken_words (or whatever the check_string arg is)
# and return them in spoken order
def getTextMatches(match_item, check_string, whole_words_only=False):
  check_string = check_string.lower()

  # If we're given a list, we'll check for everything in that list, and return it in the order that it was spoken
  # We split the input string into words, so that we only match whole words
  if type(match_item) is list:
    if whole_words_only:
      matches = [phrase for phrase in match_item if(phrase.lower() in check_string.split(" "))]
      matches.sort(key=lambda phrase: check_string.find(phrase.lower()))
      return(matches)
    else:
      matches = [phrase for phrase in match_item if(phrase.lower() in check_string)]
      matches.sort(key=lambda phrase: check_string.find(phrase.lower()))
      return(matches)
  # If it's a string, check for it as a standalone word
  elif type(match_item) is str:
    # This converts the string into a list so that we only get whole word matches
    # Otherwise, "what's 8 times 12" would count as valid for checking the "time"
    # TODO: In the list section, check if phrases are only a single word, and use this logic
    # if so, otherwise use the current checking logic.
    if whole_words_only:    
      if match_item in check_string.split(" "):
        return(match_item)
    else:
      if match_item in check_string:
        return(match_item)
    return("")

# Bloob Cores need to take the host, port, username/password of the MQTT broker, and device-id as args, this automates that.
def coreArgParse():
  import argparse

  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument('--host', default="localhost")
  arg_parser.add_argument('--port', default=1883, type=int)
  arg_parser.add_argument('--user')
  arg_parser.add_argument('--pass')
  arg_parser.add_argument('--device-id', default="test")
  arguments = arg_parser.parse_args()
  return arguments

class Intent:
  def __init__(self, id: str, core_id: str, advanced_keyphrases: list=None, keyphrases: list=None, prefixes: list=None, suffixes: list=None, variables: dict=None, numbers: dict=None, wakewords: list=None):
    self.id = id
    self.core_id = core_id
    self.advanced_keyphrases = advanced_keyphrases
    self.keyphrases = keyphrases
    self.prefixes = prefixes
    self.suffixes = suffixes
    self.variables = variables
    self.numbers = numbers
    self.wakewords = wakewords

  def asdict(self):
    intent_dict = {
      "id": self.id,
      "core_id": self.core_id,
    }
    if self.advanced_keyphrases != None:
      intent_dict["advanced_keyphrases"] = self.advanced_keyphrases
    if self.keyphrases != None:
      intent_dict["keyphrases"] = self.keyphrases
    if self.prefixes != None:
      intent_dict["prefixes"] = self.prefixes
    if self.suffixes != None:
      intent_dict["suffixes"] = self.suffixes
    if self.variables != None:
      intent_dict["variables"] = self.variables
    if self.numbers != None:
      intent_dict["numbers"] = self.numbers
    if self.wakewords != None:
      intent_dict["wakewords"] = self.wakewords

    return intent_dict

class CoreConfig:
  def __init__(self, core_id: str, friendly_name: str=None, link: str=None, author: str=None, icon: str=None, description: str=None, version: str=None, license: str=None, example_config: dict=None):
    self.core_id = core_id
    self.friendly_name = friendly_name
    self.link = link
    self.author = author
    self.icon = icon
    self.description = description
    self.version = version
    self.license = license
    self.example_config = example_config

    self.metadata = {
      "core_id": self.core_id,
      "friendly_name": self.friendly_name,
      "link": self.link,
      "author": self.author,
      "icon": self.icon,
      "description": self.description,
      "version": self.version,
      "license": self.license,
      "example_config": self.example_config
    }

  def asdict(self):
    return {
      "metadata": self.metadata
    }

class Collection:
  def __init__(self, id: str, advanced_keyphrases: list=None, keyphrases: list=None, variables: dict=None):
    self.id = id
    self.advanced_keyphrases = advanced_keyphrases
    self.keyphrases = keyphrases
    self.variables = variables

  def asdict(self):
    collection_dict = {
      "id": self.id
    }
    if self.advanced_keyphrases != None:
      collection_dict["advanced_keyphrases"] = self.advanced_keyphrases
    if self.keyphrases != None:
      collection_dict["keyphrases"] = self.keyphrases
    if self.variables != None:
      collection_dict["variables"] = self.variables

    return collection_dict

class Core:
  def __init__(self, device_id: str, core_id:str, mqtt_host: str, mqtt_port: int, mqtt_user: str=None, mqtt_pass: str=None, core_config: CoreConfig=None, intents: list=None, collections: list=None):
    self.device_id = device_id
    self.core_id = core_id
    self.core_config = core_config
    self.intents = intents
    self.collections = intents
    self.mqtt_host = mqtt_host
    self.mqtt_port = mqtt_port
    self.mqtt_auth = {'username':mqtt_user, 'password':mqtt_pass} if mqtt_user != None else None

  def log(self, text_to_log):
    message_to_log = f"[{self.core_id}] {text_to_log}"
    publish.single(f"bloob/{self.device_id}/logs", payload=message_to_log, hostname=self.mqtt_host, port=self.mqtt_port, qos=bloobQOS, auth=self.mqtt_auth)
    print(message_to_log)

  ## Provide the collection_name and core_mqtt_info, and this will return a JSON decoded version of the collection.
  ## IF THE COLLECTION DOES NOT EXIST, THIS WILL BLOCK FOREVER!
  def getCollection(self, collection_name: str):
    return json.loads(subscribe.simple(f"bloob/{self.device_id}/collections/{collection_name}", hostname=self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth).payload.decode())

  def getCentralConfig(self):
    return json.loads(subscribe.simple(f"bloob/{self.device_id}/cores/{self.core_id}/central_config", hostname=self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth).payload.decode())

  ## Takes either a list of dicts or a list of Intents which will be turned into dicts
  def publishIntents(self, intents: list=None):
    if intents != None:
      self.intents = intents

    for intent in self.intents:
      if type(intent) == dict:
        publish.single(topic=f"bloob/{self.device_id}/cores/{self.core_id}/intents/{intent['id']}", payload=json.dumps(intent), qos=bloobQOS, retain=True, hostname=self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth)
      elif type(intent) == Intent:
        publish.single(topic=f"bloob/{self.device_id}/cores/{self.core_id}/intents/{intent.id}", payload=json.dumps(intent.asdict()), qos=bloobQOS, retain=True, hostname=self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth)

  def publishCollections(self, collections: list=None):
    if collections != None:
      self.collections = collections

    for collection in self.collections:
      if type(collection) == dict:
        publish.single(f"bloob/{self.device_id}/collections/{collection['id']}", json.dumps(collection), bloobQOS, True, self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth)
      elif type(collection) == Collection:
        publish.single(f"bloob/{self.device_id}/collections/{collection.id}", json.dumps(collection.asdict()), bloobQOS, True, self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth)

  def publishConfig(self, core_config: dict=None):
    if core_config != None:
      self.core_config = core_config
    if type(self.core_config) == dict:
      publish.single(topic=f"bloob/{self.device_id}/cores/{self.core_id}/config", payload=json.dumps(self.core_config), retain=True, hostname=self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth)
    elif type(self.core_config) == CoreConfig:
      publish.single(topic=f"bloob/{self.device_id}/cores/{self.core_id}/config", payload=json.dumps(self.core_config.asdict()), retain=True, hostname=self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth)

  def publishAll(self):
    if self.core_config == None:
      self.log("No Core Config, can't publish")
    else:
      self.publishConfig()

      if self.intents != None:
        self.log("Publishing Intents")
        self.publishIntents()

      if self.collections != None:
        self.log("Publishing Collections")
        self.publishCollections()

  def waitForCoreCall(self):
    return json.loads(subscribe.simple(f"bloob/{self.device_id}/cores/{self.core_id}/run", hostname=self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth).payload.decode())

  def publishCoreOutput(self, id: str, text: str, explanation: str):
    publish.single(topic=f"bloob/{self.device_id}/cores/{self.core_id}/finished", payload=json.dumps({"id": id, "text": text, "explanation": explanation}), hostname=self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth)

  def playAudioFile(self, audio_wav_b64_str: str, id: str=None):
    # Allow choosing the ID, but generally use a random one if it's not the same request as the main speech (like playing the volume change sound)
    if id == None:
      id = str(random.randint(1,30000))
    publish.single(topic=f"bloob/{self.device_id}/cores/audio_playback_util/play_file", payload=json.dumps({"id": id, "audio": audio_wav_b64_str}), hostname=self.mqtt_host, port=self.mqtt_port, auth=self.mqtt_auth)