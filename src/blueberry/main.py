#!/usr/bin/python3
import subprocess
import sys
from time import time
import requests
import json
import pathlib
import os
import uuid

# Load everything ##############################################

## Define Devices #######################
devices = []
class BaseDevice:
    def __init__(self,friendly_name, ip_address):
        self.friendly_name = friendly_name
        self.ip_address = ip_address
        devices.append(self)
    def on(self):
        raise NotImplementedError
    def off(self):
        raise NotImplementedError
    def setColour(self,rgb_list):
        raise NotImplementedError
    def setPercentage(self,percentage):
        raise NotImplementedError

class WledDevice(BaseDevice):

  def on(self):
    requests.post(f"http://{self.ip_address}/win&T=1")

  def off(self):
    requests.post(f"http://{self.ip_address}/win&T=0")

  def setColour(self,rgb_list):
    requests.post(f"http://{self.ip_address}/win&R={rgb_list[0]}&G={rgb_list[1]}&B={rgb_list[2]}")

  # TODO: Change percentage based on the current limit
  def setPercentage(self,percentage):
    requests.post(f"http://{self.ip_address}/win&A={int(percentage*2.55)}")

class TasmotaDevice(BaseDevice):
    def __init__(self, friendly_name, ip_address):
        self.friendly_name = friendly_name
        self.ip_address = ip_address
        self.request_uri = f"http://{self.ip_address}"
        if(self.ip_address.endswith("/cm")):
            self.request_uri += "?"
        else:
            self.request_uri += "&"
        devices.append(self)
    def on(self):
        requests.get(f"{self.request_uri}cmnd=Power%201")
    def off(self):
        requests.get(f"{self.request_uri}cmnd=Power%200")

class HTTPDevice(BaseDevice):
    def __init__(self, friendly_name, on_url, off_url):
        self.friendly_name = friendly_name
        self.on_url = on_url
        self.off_url = off_url
        devices.append(self)
    def on(self):
        if(self.on_url == None):
            raise NotImplementedError
        requests.get(self.on_url)
    def off(self):
        if(self.off_url == None):
            raise NotImplementedError
        requests.get(self.off_url)

# TODO: Fetch file to define devices from server on start
## Initialize the configuration for this instance ##############################
data_path = pathlib.Path(os.environ['HOME']).joinpath(".config/bloob")
server_config = None
if data_path.exists():
  print("Loading Config")
  with open(data_path.joinpath("config.json"),"r") as instance_config_json:
    instance_config = json.load(instance_config_json)
  # Attempt to download a device configuration file from the server
  download = True
  if instance_config.get("mode") == None or instance_config.get("mode") == "local":
    download = False
  if instance_config.get("server_url") == None and download == True:
    print("Critical error, invalid server_url defined in the instance configuration file. Please correct this.")
    exit(0)
  elif download == True:
    server_config = None
    config_query_uri = f"{instance_config.get('server_url')}/{instance_config.get('uuid')}/config"
    print(f"Pulling config from: {config_query_uri}")
    server_config = requests.get(config_query_uri).json()
else:
  # Create configuration directory, add skeleton config file
  print("Creating Config Directory")
  data_path.mkdir()
  template_config = {"instance_name":"Default Name","uuid":str(uuid.uuid4()), "mode":"local", "enabled_pretrained_wakewords": ["weather", "jarvis"],"location":{"lat":10,"long":10}, "stt_model":"Systran/faster-distil-whisper-small.en", "tts_model":"en_US-lessac-high","devices": {"wled": {},"tasmota":{}, "http":{}}}
  with open(data_path.joinpath("config.json"), 'w') as instance_config:
      instance_config.write(json.dumps(template_config))
  instance_config = template_config

if server_config != None:
    devices_json = server_config
else:
    if(instance_config.get("devices") == None):
        print("Devices configuration not found. Instance configuration malformed. Exiting.")
        exit(0)
    devices_json = instance_config.get("devices")

## Instantiate all devices
print("Loading Devices")
for wled_device in devices_json["wled"]:
  WledDevice(devices_json["wled"][wled_device]["friendly_name"], devices_json["wled"][wled_device]["IP"])
for tasmota_device in devices_json["tasmota"]:
  TasmotaDevice(devices_json["tasmota"][tasmota_device]["friendly_name"], devices_json["tasmota"][tasmota_device]["IP"])
for http_device in devices_json["http"]:
    HTTPDevice(devices_json["http"][http_device]["friendly_name"], devices_json["http"][http_device].get("on_url"), devices_json["http"][http_device].get("off_url"))

## Load faster-whisper #######################

from faster_whisper import download_model
from faster_whisper import WhisperModel

stt_path = data_path.joinpath("stt")

stt_model = instance_config["stt_model"]

print(f"Loading Model: {stt_model}")
if not stt_path.exists():
  print("Creating Speech-To-Text directory")
  stt_path.mkdir()
# Do this so that unfound models are automatically downloaded, but by default we aren't checking remotely at all, and the
# STT directory doesn't need to be deleted just to automatically download other models
try:
  model = WhisperModel(model_size_or_path=stt_model, device="cpu", download_root=stt_path, local_files_only = True)
except: #huggingface_hub.utils._errors.LocalEntryNotFoundError (but can't do that here since huggingfacehub not directly imported)
  print(f"Downloading Model: {stt_model}")
  model = WhisperModel(model_size_or_path=stt_model, device="cpu", download_root=stt_path)

print(f"Loaded Model: {stt_model}")

## Load Piper ###############################
tts_model = instance_config["tts_model"]

tts_path = data_path.joinpath("tts")

output_speech_wav_path = tts_path.joinpath("output_speech.wav")
#The path must be converted to a string rather than a posixpath or it breaks python-mpv
def speak(speech_text, tts_model_path=f"{tts_path}/{tts_model}.onnx", output_audio_path=str(output_speech_wav_path), play_speech=True, blocking=False):					
  subprocess.call(f'echo "{speech_text}" | {sys.executable} -m piper --data-dir {tts_path} --download-dir {tts_path} --model {tts_model_path} --output_file {output_audio_path}', stdout=subprocess.PIPE, shell=True)
  print(f"Speaking: {speech_text}")
  if play_speech:
    audio_playback_system.play(output_audio_path)
    if blocking:
      audio_playback_system.wait_for_playback()

# Create directory and download model if necessary
if not tts_path.exists():
  print("Creating TTS Data Directory")
  tts_path.mkdir()
  print("Downloading Model")
  speak("Download",tts_model_path=tts_model, play_speech=False)

## Load intent parser #######################
get_keyphrases = ["get", "what", "whats"]
set_keyphrases = ["set", "make", "makes", "turn"]
date_keyphrases = ["date", "day", "today"]
weather_keyphrases = ["weather", "hot", "cold", "temperature"]
state_bool_keyphrases = ["on", "off"]
state_brightness_keyphrases = ["brightness"]
state_percentage_keyphrases = ["percent", "%", "percentage"]

### Colour list: 
with open("resources/keywords/colours.json", 'r') as colours_json_file:
  colours_json = json.load(colours_json_file)
state_colour_keyphrases = list(colours_json["rgb"].keys())

state_keyphrases = state_bool_keyphrases + state_brightness_keyphrases + state_percentage_keyphrases + state_colour_keyphrases

## Load MPV #####################
import mpv

audio_playback_system = mpv.MPV()

## Load OpenWakeword #######################
from openwakeword import Model
from pyaudio import PyAudio, paInt16
import numpy as np
import webrtcvad
import wave

## Set Wakeword audio variables
channels = 1 # Mono since stereo would be a waste of data
sample_rate = 16000 # Required by OpenWakeWord
frame_size = 1280 # This value chosen because oww recommends 80ms frames, 16000/1280 = 12.5, 1000/12.5 = 80ms
speech_buffer_length = 1000 # 2s of audio buffer at 16khz was the default, testing out smaller to make intent recognition easier while still not cutting any text out.
vad_speech_margin_init = 16000 # The number of samples (normally 16000 for 1s) of "Not Speech" before the recording stops

vad_threshold = 0.1 #VAD set so low purely to prevent wasting time trying to understand silence. Tune manually if wanted.
vad_aggressiveness = 3 # 0-3, least to most aggressive at filtering noise

audio_recording_system = PyAudio()

vad = webrtcvad.Vad(vad_aggressiveness)

## Find the index for the device named "pipewire" to use Pipewire for resampling of the default device
audio_recording_system_info = audio_recording_system.get_host_api_info_by_index(0)
total_devices = audio_recording_system_info.get("deviceCount")
for device_index in range(total_devices):
  if audio_recording_system.get_device_info_by_host_api_device_index(0, device_index).get("name") == "pipewire":
    mic_index = audio_recording_system.get_device_info_by_host_api_device_index(0, device_index).get("index")
print(f"Found pipewire at index {mic_index}")

# Assign and create Wakeword data directory if necessary
ww_path = data_path.joinpath("ww")
if not ww_path.exists():
  print("Creating Wakeword Data Directory")
  ww_path.mkdir()

#This is turned into a str because otherwise python-mpv and faster-whisper broke
detected_speech_wav_path = str(ww_path.joinpath("detected_speech.wav"))
## TODO: Eventually get this list from the server
## TODO: Allow certain actions to be performed solely from saying certain wakewords (split into "wake"words and "action"words or something)
## Loads enabled pretrained models and all .tflite custom models in the wakeword folder
print(f"Found these OpenWakeWord Models: {[str(model) for model in ww_path.glob('*.tflite')]}")
enabled_wakewords = instance_config["enabled_pretrained_wakewords"] + [str(model) for model in ww_path.glob('*.tflite')]
## TODO: Add automatically downloading "personal wakewords" from configuration server and enabling them

### Load OpenWakeWord model
oww = Model(wakeword_models=enabled_wakewords, vad_threshold=vad_threshold, inference_framework = "tflite")
speech_buffer = []

## Open Mic:
print("Opening Mic")
mic_stream = audio_recording_system.open(format=paInt16, channels=channels, rate=sample_rate, input=True, frames_per_buffer=frame_size, input_device_index=mic_index)

## Load Intent Parser:

### Define function for checking matches between a string and lists, then ordering them
def getSpeechMatches(match_item,device_check=False, check_string=False):
  if not check_string:
    check_string = spoken_words

  if type(match_item) is list:
    if not device_check:
      matches = [phrase for phrase in match_item if(phrase in check_string)]
      matches.sort(key=lambda phrase: check_string.find(phrase))
      return(matches)
    else:
      matches = [device for device in match_item if(device.friendly_name.lower() in check_string)]
      matches.sort(key=lambda device: check_string.find(device.friendly_name.lower()))
      return(matches)
  elif type(match_item) is str:
    # This converts the string into a list so that we only get whole word matches
    # Otherwise, "what's 8 times 12" would count as valid for checking the "time"
    # TODO: In the list section, check if phrases are only a single word, and use this logic
    # if so, otherwise use the current checking logic.
    if match_item in check_string.split(" "):
      return(match_item)
    else:
      return("")

## Load cores:

### Time / Date
from datetime import datetime

## Detection loop
print("Waiting for wakeword:")
while True:

  ## Begin capturing audio
  current_frame = np.frombuffer(mic_stream.read(frame_size), dtype=np.int16)
  speech_buffer.extend(current_frame)

  ## Cut the buffer to buffer length while just doing prediction
  if len(speech_buffer) > speech_buffer_length:
    speech_buffer = speech_buffer[-speech_buffer_length:]

  # Attempt detection: if fails, loop
  prediction = oww.predict(current_frame)
  for model_name in prediction.keys():
    confidence = prediction[model_name]
    ## Upon detection:
    if confidence >= 0.5:

      #Play recording sound
      audio_playback_system.play("resources/audio/listening.wav")

      ### Feeds silence for "4 seconds" to OpenWakeWord so that it doesn't lead to repeat activations
      ### See for yourself: https://github.com/dscripka/openWakeWord/issues/37
      ### Don't disable or it will lead to approximately 2 hours and 23 minutes of confusion.
      oww.predict(np.zeros(sample_rate*4, np.int16))
      
      # Record the wakeword and the following phrase, stopping when no speech detected
      print("Recording: waiting for 1s of silence")
      vad_speech_margin = vad_speech_margin_init
      while vad_speech_margin > 0:
        current_frame = np.frombuffer(mic_stream.read(frame_size), dtype=np.int16)
        speech_buffer.extend(current_frame)

        ## Split 80ms frames in 4 (to 20ms frames) since webrtcvad requires smaller frames		
        for vad_little_frame in np.array_split(current_frame, 4):
          
          if vad.is_speech(vad_little_frame, sample_rate) == True:
            vad_speech_margin = vad_speech_margin_init
          else:
            vad_speech_margin -= 320

      #Play stopped recording sound:
      audio_playback_system.play("resources/audio/stoplistening.wav")

      print("Saving Audio")
      with wave.open(detected_speech_wav_path, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(audio_recording_system.get_sample_size(paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(speech_buffer))

# STT ########################################################
      # TODO: Send audio to STT directly rather than using a file for it. Still record audio to /dev/shm for option to replay
      # TODO: Figure out why large models (distil and normal) cause this to significantly slow down, where any other model does it instantly
      # across significantly different tiers of hardware
      segments, info = model.transcribe(detected_speech_wav_path, beam_size=5, condition_on_previous_text=False) #condition_on_previous_text=False reduces hallucinations and inference time with no downsides for our short text.

      print("Transcribing...")
      raw_spoken_words = ""
      for segment in segments:
        raw_spoken_words += segment.text
      print("Transcribed words:", raw_spoken_words)

# Word preprocessing ###########################################
      raw_spoken_words_list = raw_spoken_words.split(" ")

      spoken_words = raw_spoken_words[1:]

      # TODO: For x in list of words to replace, do this, to allow future additions
      spoken_words = spoken_words.replace("%", " percent")

      # Remove special characters from text, make lowercase
      import re
      spoken_words = re.sub('[^A-Za-z0-9 ]+', "", spoken_words).lower()

      spoken_words_list = spoken_words.split(" ")
      print("Cleaned up words:", spoken_words)

# Intent Recognition ###########################################

      if len(spoken_words) == 0:
        speak("I didn't hear any words, could you repeat that?")
      #Special case for "play" or "search" keywords for media and web queries:
      elif spoken_words_list[0] == "play":
        pass
      elif spoken_words_list[0] == "search":
        pass

      #Check if we're setting the state of something
      elif getSpeechMatches(set_keyphrases):
        # Check if the name of a device and a state were both spoken
        # TODO: Figure out a more generic way to handle device states, and devices that only support certain states
        # TODO: Split this into checking the list of devices(tm) and the list of other settable things which will come from cores,
        # 		  and split into two different decision trees from there.
        if getSpeechMatches(devices, True) and getSpeechMatches(state_keyphrases):
          # Get the spoken state and name out of the lists of all potential options
          spoken_states = getSpeechMatches(state_keyphrases)
          spoken_devices = getSpeechMatches(devices, True)

          # Apply the states
          for index, device in enumerate(spoken_devices):
            # This should mean that if only one state was spoken, it'll repeat for all mentioned devices
            try:
              spoken_state = spoken_states[index]
            except IndexError:
              pass

            # Match case not used because colours / brightness make it less good
            ### Set the state ##################
            try:
                print(f"Turning {device.friendly_name} {spoken_state}" )
                #Boolean
                if spoken_state == "on":
                  device.on()
                elif spoken_state == "off":
                  device.off()
                  print(device.friendly_name)
                # Colours / custom states
                elif spoken_state in state_colour_keyphrases:
                  device.setColour(colours_json["rgb"][spoken_state])
                # Set percentage of device (normally brightness, but could be anything else)
                elif spoken_state in state_percentage_keyphrases:
                  how_many_numbers = 0
                  for word in spoken_words_list:
                    if word.isnumeric():
                      how_many_numbers += 1
                      spoken_number = int(word)
                  if how_many_numbers == 1 and "percent" in spoken_words_list:
                    device.setPercentage(spoken_number)

                speak(f"Turning {device.friendly_name} {spoken_state}") # Sample speech, will be better
            except NotImplementedError:
                speak(f"Device {device.friendly_name} does not support that.")
      #Check if we're getting the state of something
      elif getSpeechMatches(get_keyphrases):
        ## Get the time 
        if getSpeechMatches("time"):
          now = datetime.now()
          if now.strftime('%p') == "PM":
              apm = "PM"
          else:
              apm = "PM"
          speak(f"The time is {now.strftime('%I')}:{now.strftime('%M')} {apm}")
        ## Get the date
        elif getSpeechMatches(date_keyphrases):
          months = [" January ", " February ", " March ", " April ", " May ", " June ", " July ", " August ", " September ", " October ", " November ", " December "]
          weekdays = [" Monday ", " Tuesday ", " Wednesday ", " Thursday ", " Friday ", " Saturday ", " Sunday "]
          dayNum = datetime.now().day
          month = months[(datetime.now().month)-1]
          weekday = weekdays[datetime.today().weekday()]
          speak(f"Today, it's {weekday} the {dayNum} of {month}")
        ## Get the weather (TODO: Make less basic, allow location configuration rather than 10 10)
        elif getSpeechMatches(weather_keyphrases):
          location = instance_config["location"]
          weather = requests.get(f'https://api.open-meteo.com/v1/forecast?latitude={location["lat"]}&longitude={location["long"]}&current=temperature_2m,is_day,weathercode').json()
          speak(f'Right now, its {weather["current"]["temperature_2m"]} degrees')


# Back to beginning
      print("Waiting for wakeword:")
