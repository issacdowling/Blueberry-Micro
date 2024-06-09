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

music_words = ["song", "track", "music", "sound"]

# These include some interesting mistranscriptions
intents = [
  pybloob.Intent(
    id="getCurrentSong",
    core_id=core_id,
    keyphrases=[["$get"], ["current", "playing", "now", "this"], music_words]
  ),
  pybloob.Intent(
    id="pausePlayback",
    core_id=core_id,
    keyphrases=[["pause", "puz", "unpause", "unpuz", "unpose", "resume", "regime"], music_words]
  ),
  pybloob.Intent(
    id="stopPlayback",
    core_id=core_id,
    keyphrases=[["stop"], music_words]
  ),
  pybloob.Intent(
    id="nextTrack",
    core_id=core_id,
    keyphrases=[["next", "skip"], music_words]
  ),
  pybloob.Intent(
    id="prevTrack",
    core_id=core_id,
    keyphrases=[["previous", "last", "back"], music_words]
  )
]

c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"), core_config=core_conf, intents=intents)

def getPlaybackState():
  mopidy_response_json = json.loads(requests.post(f"http://{url}:{port}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.get_state"}).text)
  return mopidy_response_json["result"]

c.publishAll()
  
while True:
  request_json = c.waitForCoreCall()
  match request_json["intent"]:
    case "getCurrentSong":
      mopidy_response_json = json.loads(requests.post(f"http://{url}:{port}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.get_current_track"}).text)
      if mopidy_response_json["result"] == None:
        c.publishCoreOutput(request_json["id"], f"Nothing is playing right now", f"The Music (Mopidy) Core found that no song is playing")  
      else:
        current_song = mopidy_response_json["result"]["name"]
        current_artist = mopidy_response_json["result"]["artists"][0]["name"]
        c.publishCoreOutput(request_json["id"], f"The current song is {current_song} by {current_artist}", f"The Music (Mopidy) Core got that the current song is {current_song} by {current_artist}")

    case "pausePlayback":
      match getPlaybackState():
        case "paused":
          c.publishCoreOutput(request_json["id"], f"I'll unpause the music", f"The Music (Mopidy) Core unpaused the music")
          mopidy_response_json = json.loads(requests.post(f"http://{url}:{port}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.resume"}).text)
        case "playing":
          c.publishCoreOutput(request_json["id"], f"I'll pause the music", f"The Music (Mopidy) Core paused the music")
          mopidy_response_json = json.loads(requests.post(f"http://{url}:{port}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.pause"}).text)
        case "stopped":
          c.publishCoreOutput(request_json["id"], f"Nothing is playing right now", f"The Music (Mopidy) Core was asked to pause the music, but nothing is playing")

    case "stopPlayback":
      match getPlaybackState():
        case "paused" | "playing":
          mopidy_response_json = json.loads(requests.post(f"http://{url}:{port}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.stop"}).text)
          c.publishCoreOutput(request_json["id"], f"I'll stop the music", f"The Music (Mopidy) Core stopped the music")
        case _:
          c.publishCoreOutput(request_json["id"], f"Nothing is playing right now", f"The Music (Mopidy) Core was asked to stop the music, but nothing is playing")

    case "nextTrack":
      match getPlaybackState():
        case "paused" | "playing":
          mopidy_response_json = json.loads(requests.post(f"http://{url}:{port}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.next"}).text)
          c.publishCoreOutput(request_json["id"], f"I'll skip this track", f"The Music (Mopidy) Core skipped to the next track")
        case _:
          c.publishCoreOutput(request_json["id"], f"Nothing is playing right now", f"The Music (Mopidy) Core was asked to skip the music, but nothing is playing")

    case "prevTrack":
      match getPlaybackState():
        case "paused" | "playing":
          mopidy_response_json = json.loads(requests.post(f"http://{url}:{port}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.previous"}).text)
          c.publishCoreOutput(request_json["id"], f"I'll go back a track", f"The Music (Mopidy) Core went back to the previous track")
        case _:
          c.publishCoreOutput(request_json["id"], f"Nothing is playing right now", f"The Music (Mopidy) Core was asked to go back a track, but nothing is playing")