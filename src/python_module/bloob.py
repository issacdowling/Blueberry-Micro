import paho.mqtt.publish as publish
import paho.mqtt.subscribe as subscribe
import json

# Logging data should be set as a tuple, logging_data = (mqtt_host: str, mqtt_port: int, device_id: str, core_id: str)
# The point is to shorten what needs to be written and reduce duplication
def log(text_to_log, logging_data):
  mqtt_host, mqtt_port, device_id, core_id = logging_data
  message_to_log = f"[{core_id}] {text_to_log}"
  publish.single(f"bloob/{device_id}/logs", payload=message_to_log, hostname=mqtt_host, port=mqtt_port, qos=1)
  print(message_to_log)

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

class coreMQTTInfo:
  def __init__(self, device_id: str, core_id:str, mqtt_host: str, mqtt_port: int, mqtt_auth: dict):
    self.device_id = device_id
    self.core_id = core_id
    self.mqtt_host = mqtt_host
    self.mqtt_port = mqtt_port
    self.mqtt_auth = mqtt_auth


def pahoMqttAuthFromArgs(arguments):
  return {'username':arguments.user, 'password':arguments.__dict__.get("pass")} if arguments.user != None else None

## Provide the collection_name and core_mqtt_info, and this will return a JSON decoded version of the collection.
## IF THE COLLECTION DOES NOT EXIST, THIS WILL BLOCK FOREVER!
def getCollection(collection_name: str, core_mqtt_info: coreMQTTInfo):
  return json.loads(subscribe.simple(f"bloob/{core_mqtt_info.device_id}/collections/{collection_name}", hostname=core_mqtt_info.mqtt_host, port=core_mqtt_info.mqtt_port, auth=core_mqtt_info.mqtt_auth).payload.decode())

def getCentralConfig(core_mqtt_info: coreMQTTInfo):
  return json.loads(subscribe.simple(f"bloob/{core_mqtt_info.device_id}/cores/{core_mqtt_info.core_id}/central_config", hostname=core_mqtt_info.mqtt_host, port=core_mqtt_info.mqtt_port, auth=core_mqtt_info.mqtt_auth).payload.decode())