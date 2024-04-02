#!/bin/env python3
""" MQTT connected date / time getter core for Blueberry
Core ID: date_time_get

Follows the Bloob Core format for input / output

Returns the date if your query includes date, time if your query includes the time, and both if it includes both / neither.
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
import signal

import paho.mqtt.subscribe as subscribe
import paho.mqtt.publish as publish

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")
arg_parser.add_argument('--identify', default="")
arguments = arg_parser.parse_args()

arguments.port = int(arguments.port)

core_id = "date_time_get"

if arguments.identify:
  print(json.dumps({"id": core_id, "roles": ["intent_handler"]}))
  exit()

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Date / Time Getter",
    "link": None,
    "author": None,
    "icon": None,
    "description": None,
    "version": 0.1,
    "license": "AGPLv3"
  },
  "intents": [{
    "intent_name" : "getDate",
    "keywords": [["day", "date", "time"]],
    "collections": [["get"]],
    "core_id": core_id,
    "private": True
  }]
  
}

publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, hostname=arguments.host, port=arguments.port)


from datetime import datetime

def get_date():
  months = [" January ", " February ", " March ", " April ", " May ", " June ", " July ", " August ", " September ", " October ", " November ", " December "]
  weekdays = [" Monday ", " Tuesday ", " Wednesday ", " Thursday ", " Friday ", " Saturday ", " Sunday "]
  dayNum = datetime.now().day
  month = months[(datetime.now().month)-1]
  weekday = weekdays[datetime.today().weekday()]
  return str(dayNum), month, weekday

def get_time():
  now = datetime.now()
  if now.strftime('%p') == "PM":
    apm = "PM"
  else:
    apm = "PM"
  hr12 = now.strftime('%I')
  hr24 = now.strftime('%H')
  minute = now.strftime('%M') 
  return hr24, hr12, minute, apm

# Clears the published config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
def on_exit(*args):
  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
  exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

while True:
  request_json = json.loads(subscribe.simple(f"bloob/{arguments.device_id}/cores/{core_id}/run", hostname=arguments.host, port=arguments.port).payload.decode())
  if "date" in request_json["text"] and "time" not in request_json["text"]:
    dayNum, month, weekday = get_date()
    if dayNum[-1] == "1":
      dayNum += "st"
    elif dayNum[-1] == "2":
      dayNum += "nd"
    elif dayNum[-1] == "3":
      dayNum += "rd"
    else:
      dayNum += "th"
    to_speak = f"Today, it's {weekday} the {dayNum} of {month}"

      
    explanation = f"Got that the current date is the {dayNum} of {month}, which is a {weekday}"
  elif "time" in request_json["text"] and "date" not in request_json["text"]:
    hr24, hr12, minute, apm = get_time()
    to_speak = f"The time is {hr12}:{minute} {apm}"
    explanation = f"Got that the current time is {hr12}:{minute} {apm}"
  else:
    dayNum, month, weekday = get_date()
    if dayNum[-1] == "1":
      dayNum += "st"
    elif dayNum[-1] == "2":
      dayNum += "nd"
    elif dayNum[-1] == "3":
      dayNum += "rd"
    else:
      dayNum += "th"
    hr24, hr12, minute, apm = get_time()
    to_speak = f"Right now, it's {hr12}:{minute} {apm} on {weekday} the {dayNum} of {month}"
    explanation = f"Got that the current time is {hr12}:{minute} {apm}, and the current date is {weekday} the {dayNum} of {month}"

  publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({"id": request_json['id'], "text": to_speak, "explanation": explanation, "end_type": "finish"}), hostname=arguments.host, port=arguments.port)


