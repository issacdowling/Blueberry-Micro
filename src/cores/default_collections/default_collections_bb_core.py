#!/bin/env python3
import json
import argparse

import signal

import paho.mqtt.publish as publish

import pathlib
import sys

import pybloob

core_id = "default_collections"

arguments = pybloob.coreArgParse()
c = pybloob.coreMQTTInfo(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_auth=pybloob.pahoMqttAuthFromArgs(arguments))

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

pybloob.publishConfig(core_config, c)

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

pybloob.publishCollections(collections_list, c)
