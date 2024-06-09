#!/bin/env python3
""" MQTT connected weather getter core for Blueberry
Core ID: weather

Follows the Bloob Core format for input / output

Requires centralised config with key "weather" and value of an object: {"location": [lat,long], "temperature_unit": "celsius"/"fahrenheit"}. It is recommended that your lat/long is
kept to 1dp of precision, as this should be reasonable for weather requests, while not being too specific
"""
import json
import os

import requests

import pybloob

core_id = "weather"

arguments = pybloob.coreArgParse()
c = pybloob.coreMQTTInfo(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_auth=pybloob.pahoMqttAuthFromArgs(arguments))

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Weather Getter",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/weather",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Gets the weather using Open Meteo",
    "version": 0.1,
    "license": "AGPLv3"
  } 
}

intents = [{
    "id" : "getWeather",
    "core_id": core_id,
    "keyphrases": [["$get"], ["weather", "hot", "cold", "temperature", "raining", "sun"]],
    "wakewords": ["weather"]
  }]

# Load weathercodes from the drive, which should be placed next to this .py file
script_path = os.path.abspath(os.path.dirname(__file__))
with open(f"{script_path}/weathercodes.json", "r") as weather_file:
  # File by Stellasphere, modified / shrunken to fit my needs
  wmo_codes = json.load(weather_file)

## Logging starts here
log_data = arguments.host, int(arguments.port), arguments.device_id, core_id
pybloob.log("Starting up...", log_data)

pybloob.publishConfig(core_config, c)

pybloob.publishIntents(intents, c)

## Get device configs from central config, instantiate
pybloob.log("Getting Centralised Config from Orchestrator", log_data)
central_config = pybloob.getCentralConfig(c)

while True:
  request_json = pybloob.waitForCoreCall(c)
  if central_config == {} or central_config.get("location") == None:
    pybloob.log("No location set in config", log_data)
    to_speak = "I couldn't get the weather, as you don't have a location set up in your configuration file"
    explanation = "The Weather Core could not get the weather, as the user has not configured their location"
  else:
    if central_config.get("temperature_unit") == None:
      pybloob.log("No temperature unit set, defaulting to Celsius", log_data)
      temperature_unit = "celsius"
    else:
      temperature_unit = central_config["temperature_unit"]
    latlong = central_config["location"]
    try:
      weather = requests.get(f'https://api.open-meteo.com/v1/forecast?latitude={latlong[0]}&longitude={latlong[1]}&current=temperature_2m,is_day,weathercode&temperature_unit={temperature_unit}', timeout=2).json()
      to_speak = f'Right now, its {weather["current"]["temperature_2m"]} degrees {temperature_unit} and {wmo_codes[str(weather["current"]["weathercode"])]["day"]["description"]}'
      explanation = f'The Weather Core got that the temperature is {weather["current"]["temperature_2m"]} degrees {temperature_unit} and the conditions are {wmo_codes[str(weather["current"]["weathercode"])]["day"]["description"]}'
    except (TimeoutError, ConnectionError):
      to_speak = "I couldn't contact the weather service, check your internet connection"
      explanation = "The Weather Core failed to get the weather due to being unable to contact the Open Meteo servers. The user's internet connection may be down, or the Open Meteo servers may be down"
    except:
      to_speak = "I couldn't get the weather, and I'm not sure why"
      explanation = "The Weather Core failed to get the weather for an unknown reason"   

  pybloob.publishCoreOutput(request_json["id"], to_speak, explanation, c)


