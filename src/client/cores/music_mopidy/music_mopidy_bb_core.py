#!/bin/env python3

import pybloob
import requests
import json

core_id = "music_mopidy"
arguments = pybloob.coreArgParse()

core_conf = pybloob.CoreConfig(
  core_id=core_id,
  friendly_name="Music (Mopidy)",
  link="https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/music_mopidy",
  author="Issac Dowling",
  icon=None,
  description="Controls Mopidy for music playback",
  version="0.1",
  license="AGPLv3",
  example_config={
    "base_url": "http://127.0.0.1:6680"
  }
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
  ),
  pybloob.Intent(
    id="playTrack",
    core_id=core_id,
    prefixes=["play", "play the song"]
  ),
  pybloob.Intent(
    id="playAlbum",
    core_id=core_id,
    prefixes=["play the album"]
  ),
  pybloob.Intent(
    id="playArtist",
    core_id=core_id,
    prefixes=["play the artist", "play songs by", "play tracks by", "play music by"]
  ),
  pybloob.Intent(
    id="shuffleArtist",
    core_id=core_id,
    prefixes=["shuffle the artist", "shuffle songs by", "shuffle tracks by", "shuffle music by"]
  ),
  pybloob.Intent(
    id="shuffleAlbum",
    core_id=core_id,
    prefixes=["shuffle the album"]
  )
]

c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"), core_config=core_conf, intents=intents)
central_config = c.getCentralConfig()

def getPlaybackState():
  mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.get_state"}).text)
  return mopidy_response_json["result"]

## Get Mopidy server details from central config
if central_config.get("base_url") == None:
  c.log("No Base URL found in config")
else:
  base_url = central_config["base_url"]
  c.log(f"Mopidy at {base_url}")

## Define custom search source for better search with some providers
search_source = None
if central_config != {} and central_config != None:
  # If None, default Mopidy search
  search_source_details = central_config.get("search_source")
  if search_source_details != None:
    search_source = search_source_details["source"]
    c.log(f"Custom search source in use: {search_source}")

if search_source == "jf":
  # Wishes to be provided with "url" (http://something:something), "auth" token, and user id "uid" (can be gotten from devtools in web UI)
  from fuzzywuzzy import process, fuzz

  # Define Server Info
  jfurl = search_source_details["url"]
  jfauth = search_source_details["auth"]
  user_id = search_source_details["uid"]
  headers = {"X-Emby-Token": jfauth}

  jf_songs = {}

  c.log(f"Downloading song index for {search_source}")
  ## Download remote
  remote_songs_request = requests.get(jfurl+"/Users/"+user_id+f"/Items?Recursive=true&IncludeItemTypes=Audio", headers = headers)
  received_json = json.loads(remote_songs_request.text)
  # Opens "Items" key in JSON file
  songs = received_json["Items"]
  for song in songs:
    artist = "Unknown Artist" if song.get("AlbumArtist") == None else song.get("AlbumArtist")
    album = "Unknown Album" if song.get("Album") == None else song.get("Album")

    jf_songs[song["Name"]] = song
    jf_songs[f"{song['Name']} by {artist}"] = song
    jf_songs[f"{song['Name']} from {album}"] = song

  c.log(f"Downloading Album index for {search_source}")
  jf_albums = {}
  remote_albums_request = requests.get(jfurl+"/Users/"+user_id+"/Items?Recursive=true&IncludeItemTypes=MusicAlbum", headers = headers)
  received_json = json.loads(remote_albums_request.text)
  albums = received_json["Items"]
  for album in albums:
    # For each item (one item is all the info for a specific Album),
    # add the value in the "Name" and "Id" keys to a dict
    if album.get("Name"):
      jf_albums[album["Name"]] = album

      if album.get("AlbumArtist"):
        jf_albums[f"{album['Name']} by {album['AlbumArtist']}"] = album

  c.log(f"Downloading Artist index for {search_source}")
  jf_artists = {}
  # Send get request to AlbumArtists API endpoint on the Jellyfin server with authentication
  remote_artists_request = requests.get(jfurl+"/Artists/AlbumArtists", headers = headers)
  received_json = json.loads(remote_artists_request.text)
  # Opens "Items" key in JSON file
  album_artists = received_json["Items"]
  for album_artist in album_artists:
    if album_artist.get("Name"):
      jf_artists[album_artist["Name"]] = album_artist

elif search_source == "local":
  import glob
  from fuzzywuzzy import process, fuzz
  import os
  import urllib.parse

  # Wishes to be provided with "base_dir" (directory of songs)
  base_dir = search_source_details["base_dir"]

  # Scan provided directory for things ending in music-related extensions,
  # URL encode them and put into mopidy-local URI format. Save for later searching.
  local_songs = {}

  for root, _, files_in_directory in os.walk(base_dir):

    # Handles the root being the base_dir, allowing songs directly at the root
    if root == base_dir:
      root = ""
    else:
      root = root.replace(base_dir + "/", "")
    for file in files_in_directory:

      if file.endswith(".flac") or file.endswith(".wav") or file.endswith(".mp3"):
        # Maybe in future, remove the extension first too
        if root != "":
          local_songs[file] = f"local:track:{urllib.parse.quote(root+'/'+file)}"
        else:
          local_songs[file] = f"local:track:{urllib.parse.quote(file)}"

c.publishAll()
  
while True:
  c.log("Waiting for input...")
  request_json = c.waitForCoreCall()

  try:
    match request_json["intent"]:
      case "getCurrentSong":
        mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.get_current_track"}).text)
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
            mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.resume"}).text)
          case "playing":
            c.publishCoreOutput(request_json["id"], f"I'll pause the music", f"The Music (Mopidy) Core paused the music")
            mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.pause"}).text)
          case "stopped":
            c.publishCoreOutput(request_json["id"], f"Nothing is playing right now", f"The Music (Mopidy) Core was asked to pause the music, but nothing is playing")

      case "stopPlayback":
        match getPlaybackState():
          case "paused" | "playing":
            mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.stop"}).text)
            c.publishCoreOutput(request_json["id"], f"I'll stop the music", f"The Music (Mopidy) Core stopped the music")
          case _:
            c.publishCoreOutput(request_json["id"], f"Nothing is playing right now", f"The Music (Mopidy) Core was asked to stop the music, but nothing is playing")

      case "nextTrack":
        match getPlaybackState():
          case "paused" | "playing":
            mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.next"}).text)
            c.publishCoreOutput(request_json["id"], f"I'll skip this track", f"The Music (Mopidy) Core skipped to the next track")
          case _:
            c.publishCoreOutput(request_json["id"], f"Nothing is playing right now", f"The Music (Mopidy) Core was asked to skip the music, but nothing is playing")

      case "prevTrack":
        match getPlaybackState():
          case "paused" | "playing":
            mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "core.playback.previous"}).text)
            c.publishCoreOutput(request_json["id"], f"I'll go back a track", f"The Music (Mopidy) Core went back to the previous track")
          case _:
            c.publishCoreOutput(request_json["id"], f"Nothing is playing right now", f"The Music (Mopidy) Core was asked to go back a track, but nothing is playing")

      case "playTrack":
        query_success = True
        if request_json["text"].startswith("play the song"):
          query_text = request_json["text"].replace("play the song", "")
        elif request_json["text"].startswith("play"):
          query_text = request_json["text"].replace("play", "")

        c.log(f"Searching for the track \"{query_text}\" to play")
        match search_source:
          case None:
            # Query _is_ supposed to be a list of strings... even if it's just one string.
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.library.search", "params": {"query": {"track_name": [query_text]}}}
            mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)
            if mopidy_response_json['result'][0].get("tracks") == None:
              c.publishCoreOutput(request_json["id"], f"I couldn't find any song by the name {query_text}", f"The Music (Mopidy) Core couldn't find a song named {query_text}")
              query_success = False
            else:
              found_track = mopidy_response_json['result'][0]['tracks'][0]
              track_name = found_track['name']
              track_artist = "Unknown artist" if found_track.get("artists") == None or found_track["artists"][0].get("name") == None else found_track["artists"][0]["name"]
              track_album = "Unknown album" if found_track.get("album") == None or found_track["album"].get("name") == None else found_track["album"]["name"]
              track_uri = found_track["uri"]

          case "jf":
            ## Use fuzzywuzzy to search the complete song list, set the URI to match what Mopidy is expecting
            fuzzy_result = process.extractOne(query_text, list(jf_songs.keys()), scorer=fuzz.token_sort_ratio)
            track_index, fuzzy_confidence = fuzzy_result[0], fuzzy_result[1]
            track_name = jf_songs[track_index]["Name"]
            track_artist = "Unknown Artist" if jf_songs[track_index].get("AlbumArtist") == None else jf_songs[track_index]["AlbumArtist"]
            track_album = "Unknown album" if jf_songs[track_index].get("Album") == None else jf_songs[track_index]["Album"]
            track_uri = f"jellyfin:track:{jf_songs[track_index]['Id']}"
            c.log(f"Found track {track_name} by {track_artist} with a match of {fuzzy_confidence}%")

          case "local":
            fuzzy_result = process.extractOne(query_text, list(local_songs.keys()), scorer=fuzz.token_sort_ratio)
            track_index, fuzzy_confidence = fuzzy_result[0], fuzzy_result[1]      
            track_uri = local_songs[track_index]
            # Search mopidy for metadata, as it's not guaranteed to be gleamable easily from the file itself
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.library.lookup", "params": {"uris": [track_uri]}}
            mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)
            mopidy_response_track = mopidy_response_json["result"][track_uri][0]

            track_name = "Unknown Track" if mopidy_response_track.get("name") == None else mopidy_response_track["name"]
            track_artist = "Unknown artist" if mopidy_response_track.get("album") == None or mopidy_response_track["album"].get("artists") == None else mopidy_response_track["album"]["artists"][0]["name"]
            track_album = "Unknown album" if mopidy_response_track.get("album") == None or mopidy_response_track["album"].get("name") == None else mopidy_response_track["album"]["name"]

        if query_success:
          ## Add track to the tracklist
          query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.tracklist.add", "params": {"uris": [track_uri]}}
          track_add_response = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)

          ## Play the song at the tlid (tracklist ID?) of the song(s) we just added
          query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.playback.play", "params": {"tlid": track_add_response["result"][0]["tlid"]}}
          play_tlid_response = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)

          c.publishCoreOutput(request_json["id"], f"I'll play the track {track_name} by {track_artist} from the album {track_album}", f"The Music (Mopidy) Core started playing the track {track_name} by {track_artist} from the album {track_album}")

      case "playAlbum" | "shuffleAlbum":
        query_success = True
        if request_json["text"].startswith("play the album"):
          query_text = request_json["text"].replace("play the album", "")
        elif request_json["text"].startswith("shuffle the album"):
          query_text = request_json["text"].replace("shuffle the album", "")          

        c.log(f"Searching for the album \"{query_text}\" to play")
        match search_source:
          case None | "local":
            # Query _is_ supposed to be a list of strings... even if it's just one string.
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.library.search", "params": {"query": {"album": [query_text]}}}
            mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)
            # I know that I'm looking for tracks here. No albums are showing up in responses for me, so I'ma
            # searching for songs in a specific album, and checking their album fields for the name.
            c.log(mopidy_response_json['result'][0]["tracks"][0].get("album"))
            if mopidy_response_json['result'][0].get("tracks") == None and mopidy_response_json['result'][0]["tracks"][0].get("album") == None:
              c.publishCoreOutput(request_json["id"], f"I couldn't find any album by the name {query_text}", f"The Music (Mopidy) Core couldn't find an album named {query_text}")
              query_success = False
            else:
              found_album = mopidy_response_json['result'][0]["tracks"][0]["album"]
              album_name = found_album['name']
              album_artist = "Unknown artist" if found_album.get("artists") == None or found_album["artists"][0].get("name") == None else found_album["artists"][0]["name"]
              album_uri = found_album["uri"]

          case "jf":
            ## Use fuzzywuzzy to search the complete album list, set the URI to match what Mopidy is expecting
            fuzzy_result = process.extractOne(query_text, list(jf_albums.keys()), scorer=fuzz.token_sort_ratio)
            album_index, fuzzy_confidence = fuzzy_result[0], fuzzy_result[1]
            album_name = jf_albums[album_index]["Name"]
            album_artist = "Unknown Artist" if jf_albums[album_index].get("AlbumArtist") == None else jf_albums[album_index]["AlbumArtist"]
            album_uri = f"jellyfin:album:{jf_albums[album_index]['Id']}"
            c.log(f"Found album {album_name} by {album_artist} with a match of {fuzzy_confidence}%")

        if query_success:

          # If shuffling, we first clear the tracklist before adding tracks so that we don't shuffle into previous tracks
          if request_json["intent"] == "shuffleAlbum":
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.tracklist.clear"}
            requests.post(f"{base_url}/mopidy/rpc", json=query_json)

          ## Add tracks to the tracklist
          query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.tracklist.add", "params": {"uris": [album_uri]}}
          album_add_response = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)

          # If shuffling, shuffle before playing, then play track id 1 (as we earlier cleared the tracklist), else play at the ID of the added and non-shuffled songs
          if request_json["intent"] == "shuffleAlbum":
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.tracklist.shuffle"}
            requests.post(f"{base_url}/mopidy/rpc", json=query_json)            

            ## Play the song at the tlid (tracklist ID?) of the song(s) we just added
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.playback.play", "params": {"tlid": 1}}
            play_tlid_response = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)
            speech_play_type = "shuffle"
          else:
            ## Play the song at the tlid (tracklist ID?) of the song(s) we just added
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.playback.play", "params": {"tlid": album_add_response["result"][0]["tlid"]}}
            play_tlid_response = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)
            speech_play_type = "play"

          c.publishCoreOutput(request_json["id"], f"I'll {speech_play_type} the album {album_name} by {album_artist}", f"The Music (Mopidy) Core started {speech_play_type}ing the album {album_name} by {album_artist}")

      case "playArtist" | "shuffleArtist":
        query_success = True
        if request_json["text"].startswith("play the artist"):
          query_text = request_json["text"].replace("play the artist", "")
        elif request_json["text"].startswith("play songs by"):
          query_text = request_json["text"].replace("play songs by", "")
        elif request_json["text"].startswith("play tracks by"):
          query_text = request_json["text"].replace("play tracks by", "")
        elif request_json["text"].startswith("play music by"):
          query_text = request_json["text"].replace("play music by", "")
        elif request_json["text"].startswith("shuffle the artist"):
          query_text = request_json["text"].replace("shuffle the artist", "")
        elif request_json["text"].startswith("shuffle songs by"):
          query_text = request_json["text"].replace("shuffle songs by", "")
        elif request_json["text"].startswith("shuffle tracks by"):
          query_text = request_json["text"].replace("shuffle tracks by", "")
        elif request_json["text"].startswith("shuffle music by"):
          query_text = request_json["text"].replace("shuffle music by", "")

        c.log(f"Searching for the artist \"{query_text}\" to play")
        match search_source:
          case None | "local":
            # Query _is_ supposed to be a list of strings... even if it's just one string.
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.library.search", "params": {"query": {"artist": [query_text]}}}
            mopidy_response_json = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)
            
            # I know that I'm looking for tracks here. No artists are showing up in responses for me, so I'ma
            # searching for songs made by a specific artist, and checking their artist fields for the searched artist.
            if mopidy_response_json['result'][0].get("tracks") == None and mopidy_response_json['result'][0]["tracks"][0].get("artists") == None:
              c.publishCoreOutput(request_json["id"], f"I couldn't find any artist by the name {query_text}", f"The Music (Mopidy) Core couldn't find an artist named {query_text}")
              query_success = False
            else:
              found_artist = mopidy_response_json['result'][0]["tracks"][0]["artists"][0]
              artist_name = found_artist['name']
              artist_uri = found_artist["uri"]

          case "jf":
            ## Use fuzzywuzzy to search the complete artist list, set the URI to match what Mopidy is expecting
            fuzzy_result = process.extractOne(query_text, list(jf_artists.keys()), scorer=fuzz.token_sort_ratio)
            artist_index, fuzzy_confidence = fuzzy_result[0], fuzzy_result[1]
            artist_name = jf_artists[artist_index]["Name"]
            artist_uri = f"jellyfin:artist:{jf_artists[artist_index]['Id']}"
            c.log(f"Found artist {artist_name} with a match of {fuzzy_confidence}%")

        if query_success:

          # If shuffling, we first clear the tracklist before adding tracks so that we don't shuffle into previous tracks
          if request_json["intent"] == "shuffleArtist":
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.tracklist.clear"}
            requests.post(f"{base_url}/mopidy/rpc", json=query_json)

          ## Add tracks to the tracklist
          query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.tracklist.add", "params": {"uris": [artist_uri]}}
          artist_add_response = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)

          # If shuffling, shuffle before playing, then play track id 1 (as we earlier cleared the tracklist), else play at the ID of the added and non-shuffled songs
          if request_json["intent"] == "shuffleArtist":
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.tracklist.shuffle"}
            requests.post(f"{base_url}/mopidy/rpc", json=query_json)            

            ## Play the song at the tlid (tracklist ID?) of the song(s) we just added
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.playback.play", "params": {"tlid": 1}}
            play_tlid_response = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)
            speech_play_type = "shuffle"
          else:
            ## Play the song at the tlid (tracklist ID?) of the song(s) we just added
            query_json = {"jsonrpc": "2.0", "id": 1, "method": "core.playback.play", "params": {"tlid": artist_add_response["result"][0]["tlid"]}}
            play_tlid_response = json.loads(requests.post(f"{base_url}/mopidy/rpc", json=query_json).text)
            speech_play_type = "play"

          c.publishCoreOutput(request_json["id"], f"I'll {speech_play_type} the artist {artist_name}", f"The Music (Mopidy) Core started {speech_play_type}ing the artist {artist_name}")

  except (TimeoutError, ConnectionError):
    to_speak = "I couldn't contact the music service, check your internet connection"
    explanation = "The Music Core failed to access the mopidy server. The user's internet connection may be down, or the Mopidy server may be down"
    c.publishCoreOutput(request_json["id"], to_speak, explanation)
  except Exception as e:
    c.log(e)
    to_speak = "I couldn't access your music, and I'm not sure why"
    explanation = "The Music Core failed to access the music for an unknown reason"   
    c.publishCoreOutput(request_json["id"], to_speak, explanation)