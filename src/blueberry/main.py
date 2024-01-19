#!/usr/bin/python3
import subprocess
import sys
from time import time
import requests
import json

# Load everything ##############################################

## Define Devices #######################
devices = []
class WledDevice:
  def __init__(self,friendly_name, ip_address):
    self.friendly_name = friendly_name
    self.ip_address = ip_address
    devices.append(self)

  def on(self):
    requests.post(f"http://{self.ip_address}/win&T=1")

  def off(self):
    requests.post(f"http://{self.ip_address}/win&T=0")

  def setColour(self,rgb_list):
    requests.post(f"http://{self.ip_address}/win&R={rgb_list[0]}&G={rgb_list[1]}&B={rgb_list[2]}")

  # TODO: Change percentage based on the current limit
  def setPercentage(self,percentage):
    requests.post(f"http://{self.ip_address}/win&A={int(percentage*2.55)}")

class TasmotaDevice:
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
# TODO: Fetch file to define devices from server on start

with open("resources/devices.json", 'r') as devices_json_file:
  devices_json = json.load(devices_json_file)


## Instantiate all devices
for wled_device in devices_json["wled"]:
  WledDevice(devices_json["wled"][wled_device]["friendly_name"], devices_json["wled"][wled_device]["IP"])
for tasmota_device in devices_json["tasmota"]:
  TasmotaDevice(devices_json["tasmota"][tasmota_device]["friendly_name"], devices_json["tasmota"][tasmota_device]["IP"])

## Load faster-whisper #######################

from faster_whisper import WhisperModel

stt_model = "small.en"

print(f"Loading Model: {stt_model}")
model = WhisperModel(stt_model, device="cpu")

print(f"Loaded Model: {stt_model}")

## Load Piper ###############################
tts_data_dir = "tts_data"

def speak(speech_text, tts_model=f"{tts_data_dir}/en_US-lessac-high.onnx", output_audio_path=f"{tts_data_dir}/output_speech.wav", play_speech=True):					
  subprocess.call(f'echo "{speech_text}" | {sys.executable} -m piper --data-dir {tts_data_dir} --download-dir {tts_data_dir} --model {tts_model} --output_file {output_audio_path}', stdout=subprocess.PIPE, shell=True)
  print(f"Speaking: {speech_text}")
  if play_speech:
    subprocess.call(f'aplay {output_audio_path}', stdout=subprocess.PIPE, shell=True)

## Load intent parser #######################
get_keyphrases = ["get", "what", "whats"]
set_keyphrases = ["set", "make", "makes", "turn"]
state_bool_keyphrases = ["on", "off"]
state_brightness_keyphrases = ["brightness"]
state_percentage_keyphrases = ["percent", "%", "percentage"]

### Colour list: 
with open("resources/keywords/colours.json", 'r') as colours_json_file:
  colours_json = json.load(colours_json_file)
state_colour_keyphrases = list(colours_json["rgb"].keys())

state_keyphrases = state_bool_keyphrases + state_brightness_keyphrases + state_percentage_keyphrases + state_colour_keyphrases

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

detected_speech_wav_path = "testoutput.wav"

audio_system = PyAudio()

vad = webrtcvad.Vad(vad_aggressiveness)

## Find the index for the device named "pipewire" to use Pipewire for resampling of the default device
audio_system_info = audio_system.get_host_api_info_by_index(0)
total_devices = audio_system_info.get("deviceCount")
for device_index in range(total_devices):
  if audio_system.get_device_info_by_host_api_device_index(0, device_index).get("name") == "pipewire":
    mic_index = audio_system.get_device_info_by_host_api_device_index(0, device_index).get("index")
print(f"Found pipewire at index {mic_index}")

## TODO: Eventually get this list from the server
enabled_wakewords = ["weather", "ww_data/personal_wakewords/50000-50000blueberry.tflite"] #breaks if not ran from /src
## TODO: Add automatically downloading "personal wakewords" from configuration server and enabling them

### Load OpenWakeWord model
oww = Model(wakeword_models=enabled_wakewords, vad_threshold=vad_threshold, inference_framework = "tflite")
speech_buffer = []

## Open Mic:
print("Opening Mic")
mic_stream = audio_system.open(format=paInt16, channels=channels, rate=sample_rate, input=True, frames_per_buffer=frame_size, input_device_index=mic_index)

## Load Intent Parser:

### Define function for checking matches between a string and lists, then ordering them
def getSpeechMatches(match_list,device_check=False, check_string=False):
  if not check_string:
    check_string = spoken_words

  if not device_check:
    matches = [phrase for phrase in match_list if(phrase in check_string)]
    matches.sort(key=lambda phrase: check_string.find(phrase))
    return(matches)
  else:
    matches = [device for device in match_list if(device.friendly_name.lower() in check_string)]
    matches.sort(key=lambda device: check_string.find(device.friendly_name.lower()))
    return(matches)

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

      #Play recording sound (eventually probably use an actual library):
      subprocess.call(f'aplay resources/audio/listening.wav', stdout=subprocess.PIPE, shell=True)

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

      #Play stopped recording sound (eventually probably use an actual library):
      subprocess.call(f'aplay resources/audio/stoplistening.wav', stdout=subprocess.PIPE, shell=True)

      print("Saving Audio")
      with wave.open(detected_speech_wav_path, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(audio_system.get_sample_size(paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(speech_buffer))

# STT ########################################################
      # TODO: Send audio to STT directly rather than using a file for it. Still record audio to /dev/shm for option to replay
      segments, info = model.transcribe(detected_speech_wav_path, beam_size=5)

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
            print(f"Turning {device.friendly_name} {spoken_state}" )
            #Boolean
            if spoken_states[0] == "on":
              device.on()
            elif spoken_states[0] == "off":
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

      #Check if we're getting the state of something
      elif list_of_spoken_words[0] in getKeyWords:
        ## Get the time 
        if "time" in list_of_spoken_words:
          now = datetime.now()
          if now.strftime('%p') == "PM":
              apm = "PM"
          else:
              apm = "PM"
          speak(f"The time is {now.strftime('%I')}:{now.strftime('%M')} {apm}")
        ## Get the date
        elif "date" in list_of_spoken_words or "day" in list_of_spoken_words or "today" in list_of_spoken_words:
          months = [" January ", " February ", " March ", " April ", " May ", " June ", " July ", " August ", " September ", " October ", " November ", " December "]
          weekdays = [" Monday ", " Tuesday ", " Wednesday ", " Thursday ", " Friday ", " Saturday ", " Sunday "]
          dayNum = datetime.now().day
          month = months[(datetime.now().month)-1]
          weekday = weekdays[datetime.today().weekday()]
          speak(f"Today, it's {weekday} the {dayNum} of {month}")
        ## Get the weather (TODO: Make less basic, allow location configuration rather than 10 10)
        elif "weather" in list_of_spoken_words or "hot" in list_of_spoken_words or "cold" in list_of_spoken_words:
          weather = requests.get(f'https://api.open-meteo.com/v1/forecast?latitude=10&longitude=10&current=temperature_2m,is_day,weathercode').json()
          speak(f'Right now, its {weather["current"]["temperature_2m"]} degrees')


# Back to beginning
      print("Waiting for wakeword:")