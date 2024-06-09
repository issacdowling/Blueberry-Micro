#!/bin/env python3
""" MQTT connected date / time getter core for Blueberry
Core ID: date_time_get

Follows the Bloob Core format for input / output

Returns the date if your query includes date, time if your query includes the time, and both if it includes both / neither.
"""

import pybloob

core_id = "calc"

arguments = pybloob.coreArgParse()
c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"))

add_words = ["add", "plus"]
minus_words = ["minus", "take"]
multiply_words = ["times", "multiplied"]
divide_words = ["over", "divide"]

core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Very Basic Calculator",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/calc",
    "author": "Issac Dowling",
    "icon": None,
    "description": "A very very simple calculator Core",
    "version": 0.1,
    "license": "AGPLv3"
  }
}

c.publishConfig(core_config)

intents = [{
    "id" : "calc",
    "keyphrases": [["$get"], add_words + minus_words + multiply_words + divide_words],
    "numbers": {"any": "any"},
    "core_id": core_id
  }]

c.publishIntents(intents)

while True:
  request_json = c.waitForCoreCall()
  numbers = []
  for word in request_json["text"].split(" "):
    if word.isnumeric(): numbers.append(int(word))

  if len(numbers) == 2:
    if pybloob.getTextMatches(match_item=add_words, check_string=request_json["text"]):
      operator = " plus "
      result = numbers[0] + numbers[1]
    elif pybloob.getTextMatches(match_item=minus_words, check_string=request_json["text"]):
      operator = " minus "
      result = numbers[0] - numbers[1]
    elif pybloob.getTextMatches(match_item=divide_words, check_string=request_json["text"]):
      operator = " divided by "
      result = numbers[0] / numbers[1]
    elif pybloob.getTextMatches(match_item=multiply_words, check_string=request_json["text"]):
      operator = " multiplied by "
      result = numbers[0] * numbers[1]

    to_speak = f'{numbers[0]} {operator} {numbers[1]} equals {str(result).replace(".", " point ")}'
    explanation = f'Calculator Core got that {numbers[0]} {operator} {numbers[1]} equals {str(result).replace(".", " point ")}'

  else:
    to_speak = f"You didn't say 2 numbers, you said {len(numbers)}"
    explanation = f"Calculator failed, as the user didn't say the 2 required numbers, they said {len(numbers)}"

  c.publishCoreOutput(request_json["id"], to_speak, explanation)
