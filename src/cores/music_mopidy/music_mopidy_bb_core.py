#!/bin/env python3

import pybloob
import requests
import json

core_id = "music_mopidy"
arguments = pybloob.coreArgParse()

url, port = "localhost", 6680

core_conf = pybloob.CoreConfig(
  core_id=core_id,
  friendly_name="Music (Mopidy)",
  link="https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/music_mopidy",
  author="Issac Dowling",
  icon=None,
  description="Controls Mopidy for music playback",
  version="0.1",
  license="AGPLv3",
  example_config=None
)

intents = [
  pybloob.Intent(
    id="getCurrentSong",
    core_id=core_id,
    keyphrases=[["$get"], ["current", "playing", "now"], ["song", "track", "music"]]
  )
]

c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"), core_config=core_conf, intents=intents)

c.publishAll()

while True:
  request_json = c.waitForCoreCall()
  if request_json["intent"] == "getCurrentSong":
    mopidy_response_json = json.loads(requests.post(f"http://{url}:{port}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.get_current_track"}).text)
    if mopidy_response_json["result"] == None:
      c.publishCoreOutput(request_json["id"], f"Nothing is playing right now", f"The Music (Mopidy) Core found that no song is playing")  
    else:
      current_song = mopidy_response_json["result"]["name"]
      current_artist = mopidy_response_json["result"]["artists"][0]["name"]
      c.publishCoreOutput(request_json["id"], f"The current song is {current_song} by {current_artist}", f"The Music (Mopidy) Core got that the current song is {current_song} by {current_artist}")