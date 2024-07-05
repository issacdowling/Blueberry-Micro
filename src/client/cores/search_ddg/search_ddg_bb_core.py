#!/bin/env python3
""" MQTT connected weather getter core for Blueberry
Core ID: weather

Follows the Bloob Core format for input / output

Requires centralised config with key "weather" and value of an object: {"location": [lat,long], "temperature_unit": "celsius"/"fahrenheit"}. It is recommended that your lat/long is
kept to 1dp of precision, as this should be reasonable for weather requests, while not being too specific
"""

from duckduckgo_search import DDGS

import pybloob

core_id = "search_ddg"

arguments = pybloob.coreArgParse()
c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"))

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Web Search (DuckDuckGo)",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/search_ddg",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Searches the web using DuckDuckGo.",
    "version": 0.1,
    "license": "AGPLv3"
  }
}

intents = [{
    "id" : "search_ddg",
    "core_id": core_id,
    "prefixes": ["search"]
  }]

c.log("Starting up...")

c.publishConfig(core_config)

c.publishIntents(intents)

## Get device configs from central config, instantiate
c.log("Getting Centralised Config from Orchestrator")
central_config = c.getCentralConfig()

## TODO: Add (option?) sending a link to the search and results through ntfy for getting more info
while True:
  request_json = c.waitForCoreCall()
  text_to_speak = DDGS().text(request_json["text"][1:], max_results=1)[0]["body"]
  explanation = "A DuckDuckGo search returned: " + text_to_speak
  c.publishCoreOutput(request_json["id"], text_to_speak, explanation)