#!/bin/env python3
""" Basic greeter core for Blueberry
Core ID: greet_demo

Says hi back to you.
"""
import json

import pybloob

core_id = "greet"

arguments = pybloob.coreArgParse()
c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"))

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Greeting Demo",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/greet_demo",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Says hi back to you",
    "version": 0.1,
    "license": "AGPLv3"
  }
}

intents = [{
    "id" : "helloGreet",
    "keyphrases": [["hello", "hi"]],
    "core_id": core_id
  }]

c.publishConfig(core_config)

c.publishIntents(intents)

while True:
  request_json = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/run", hostname=arguments.host, port=arguments.port).payload.decode())
  greeting = "Hello, World!"
  c.publishCoreOutput(request_json["id"], greeting, f"The Greeting Core says {greeting}")
