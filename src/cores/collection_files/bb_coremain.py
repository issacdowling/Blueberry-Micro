#!/bin/env python3
import json
import argparse

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id', default="test")
arg_parser.add_argument('--identify', default="")
arg_parser.add_argument('--collections', default="")
arguments = arg_parser.parse_args()

arguments.port = int(arguments.port)

colour_collection = {
  "id": "colours",
  "keywords": [
      "red",
      "orange",
      "yellow",
      "green",
      "blue",
      "indigo",
      "violet",
      "teal",
      "salmon",
      "purple",
      "pink",
      "navy",
      "lime",
      "gold",
      "cyan",
      "coral",
      "white"
  ],
  "substitute": None,
    "variables": {
        "red": [
            255,
            0,
            0
        ],
        "orange": [
            255,
            165,
            0
        ],
        "yellow": [
            255,
            255,
            0
        ],
        "green": [
            0,
            255,
            0
        ],
        "blue": [
            0,
            0,
            255
        ],
        "indigo": [
            75,
            0,
            130
        ],
        "violet": [
            238,
            130,
            238
        ],
        "teal": [
            0,
            128,
            128
        ],
        "salmon": [
            250,
            128,
            114
        ],
        "purple": [
            128,
            0,
            128
        ],
        "pink": [
            255,
            192,
            203
        ],
        "navy": [
            0,
            0,
            128
        ],
        "lime": [
            0,
            255,
            0
        ],
        "gold": [
            255,
            215,
            0
        ],
        "cyan": [
            0,
            255,
            255
        ],
        "coral": [
            255,
            127,
            80
        ],
        "white": [
            255,
            255,
            255
        ]
    }
}

boolean_collection = {
    "id": "boolean",
  "keywords": [
    "on",
    "true",
    "yes",
    "agreed",
    "agree",
    "sure",
    "alright",
    "off",
    "false",
    "no",
    "disagreed",
    "disagree",
    "nope",
    "dont"
  ],
  "substitute": None,
  "variables": {
    "on": True,
    "true": True,
    "yes": True,
    "agreed": True,
    "agree": True,
    "sure": True,
    "alright": True,
    "off": False,
    "false": False,
    "no": False,
    "disagreed": False,
    "disagree": False,
    "nope": False,
    "dont": False
  }
}

set_collection = {
    "id": "set",
  "keywords": [
    "set",
    "turn",
    "make"
  ],
  "substitute": None,
  "variables": {
  }
}

get_collection = {
    "id": "get",
  "keywords": [
    "get",
    "what",
    "is",
    "tell me"
  ],
  "substitute": None,
  "variables": {
  }
}



any_number_collection = {
    "id": "any_number",
    "placeholder": "This is only used to add the any_number Collection to the loaded_collections. The intent_handler has a special case for checking numbers."
}
collections_list = [colour_collection, any_number_collection, boolean_collection, set_collection, get_collection]

core_id = "basic_collections"

if arguments.identify:
  print(json.dumps({"id": core_id, "roles": ["collection_handler"]}))
  exit()

if arguments.collections:
  print(json.dumps({"collections": collections_list}))
  exit()