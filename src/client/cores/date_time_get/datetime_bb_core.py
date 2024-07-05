#!/bin/env python3
""" MQTT connected date / time getter core for Blueberry
Core ID: date_time_get

Follows the Bloob Core format for input / output

Returns the date if your query includes date, time if your query includes the time, and both if it includes both / neither.
"""



import pybloob

core_id = "datetime"

arguments = pybloob.coreArgParse()
c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"))

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Date / Time Getter",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/date_time_get",
    "author": "Issac Dowling",
    "icon": None,
    "description": None,
    "version": 0.1,
    "license": "AGPLv3"
  }  
}

intents = [{
    "id" : "getDate",
    "keyphrases": [["$get"], ["day", "date", "time"]],
    "core_id": core_id
  }]

c.publishConfig(core_config)

c.publishIntents(intents)

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

while True:
  request_json = c.waitForCoreCall()
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

  c.publishCoreOutput(request_json["id"], to_speak, explanation)


