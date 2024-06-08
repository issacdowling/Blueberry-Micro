#!/bin/env python3
import json
import argparse

import signal

import paho.mqtt.publish as publish

import pathlib
import sys

import pybloob

arguments = pybloob.coreArgParse()

core_id = "default_collections"

core_config = {
	"metadata": {
		"core_id": core_id,
		"friendly_name": "Default Collections",
		"link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/default_collections",
		"author": "Issac Dowling",
		"icon": None,
		"description": "Provides preset Collections that may be useful",
		"version": "0.1",
		"license": "AGPLv3"
	}
}

# Clears the published Collections and Config on exit, representing that the core is shut down, and shouldn't be picked up by the intent parser
def on_exit(*args):
	pybloob.log("Shutting Down...", log_data)
	publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/collections", payload=None, retain=True, hostname=arguments.host, port=arguments.port)
	publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=None, retain=True, hostname=arguments.host, port=arguments.port)

	exit()

signal.signal(signal.SIGTERM, on_exit)
signal.signal(signal.SIGINT, on_exit)

publish.single(topic=f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, hostname=arguments.host, port=arguments.port)

colour_collection = {
	"id": "colours",
	"keyphrases": [
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
	"keyphrases": [
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
	"keyphrases": [
		"set",
		"turn",
		"make",
	]
}

get_collection = {
	"id": "get",
	"keyphrases": [
		"get",
		"what",
		"whats",
		"is",
		"tell me",
		"how"
	]
}

collections_list = [colour_collection, boolean_collection, set_collection, get_collection]

for collection in collections_list:
	publish.single(f"bloob/{arguments.device_id}/collections/{collection['id']}", json.dumps(collection), 2, True)
