#!/usr/bin/python3
import subprocess
import sys
from time import time
import requests
import json

# Device controls ##############################################
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

# TODO: File to define devices instead
door_light = WledDevice("Name", "IP")
bedside_light = WledDevice("Name", "IP")

# Wakeword ########################################################
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

## Eventually get this list from the server
enabled_wakewords = ["weather", "ww_data/personal_wakewords/50000-50000blueberry.tflite"] #breaks if not ran from /src

## TODO: Add automatically downloading "personal wakewords" from configuration server and enabling them
print("Opening Mic")
mic_stream = audio_system.open(format=paInt16, channels=channels, rate=sample_rate, input=True, frames_per_buffer=frame_size, input_device_index=mic_index)


## Detection loop
oww = Model(wakeword_models=enabled_wakewords, vad_threshold=vad_threshold, inference_framework = "tflite")
speech_buffer = []

print("Waiting for wakeword:")
while True:

	## Begin capturing audio
	current_frame = np.frombuffer(mic_stream.read(frame_size), dtype=np.int16)
	speech_buffer.extend(current_frame)

	## Cut the buffer to 2s while just doing prediction
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

			print("Sending Audio")
			# TODO: Send to STT
			with wave.open(detected_speech_wav_path, 'wb') as wf:
				wf.setnchannels(channels)
				wf.setsampwidth(audio_system.get_sample_size(paInt16))
				wf.setframerate(sample_rate)
				wf.writeframes(b''.join(speech_buffer))

# STT ########################################################
			from faster_whisper import WhisperModel

			stt_model = "base.en"

			print(f"Loading Model: {stt_model}")
			model = WhisperModel(stt_model, device="cpu")

			print(f"Loaded Model: {stt_model}")

			segments, info = model.transcribe(detected_speech_wav_path, beam_size=5)

			print("Transcribing...")
			raw_spoken_words = ""
			for segment in segments:
				raw_spoken_words += segment.text
			print("Transcribed.")
			print(raw_spoken_words)
# Intent Recognition ###########################################
			# Remove special characters from text, make lowercase, split into list, remove the initial space character
			import re 
			list_of_spoken_words = re.sub('[^A-Za-z0-9 ]+', "", raw_spoken_words).lower().split(" ")
			list_of_spoken_words.pop(0)

			print(list_of_spoken_words)

			setKeyWords = ["set", "make", "turn"]
			stateBoolKeywords = ["on", "off"]
			stateBrightnessKeywords = ["brightness"]
			stateColourKeywords = ["colour", "color"] #This is bad, eventually a big list of colours should be put here, with conversions to RGB for applying to lights.
			stateKeyWords = stateBoolKeywords + stateBrightnessKeywords + stateColourKeywords
			#Special case for "play" or "search" keywords for media and web queries:
			if list_of_spoken_words[0] == "play":
				pass
			elif list_of_spoken_words[0] == "search":
				pass

			#Check if we're setting the state of something
			elif list_of_spoken_words[0] in setKeyWords:
				# If the name of a device and a state were both spoken, apply that state to that device
				# TODO: Support more than just on/off
				if (len(set(list_of_spoken_words).intersection([device.friendly_name.lower() for device in devices])) == 1) and (len(set(list_of_spoken_words).intersection(stateKeyWords)) == 1):
					# Get the spoken state and name out of the lists of all potential options
					spoken_state = list(set(list_of_spoken_words).intersection(stateKeyWords))[0]
					spoken_device_name = list(set(list_of_spoken_words).intersection([device.friendly_name.lower() for device in devices]))[0]

					#Actually perform changing the state
					print(f"Turning {spoken_device_name} {spoken_state}" )
					for device in devices:
						if device.friendly_name.lower() == spoken_device_name:
							if spoken_state == "on":
								device.on()
							elif spoken_state == "off":
								device.off()


# TTS ########################################################

## Test TTS by speaking on launch
					speech_text = f"Turning {spoken_device_name} {spoken_state}" # Sample speech, will be better
					tts_data_dir = "tts_data"
					tts_model = f"{tts_data_dir}/en_US-lessac-high.onnx" # If this is a path, it will be loaded directly, but if it's just the name, it will redownload every time. https://github.com/rhasspy/piper to download.

					subprocess.call(f'echo "{speech_text}" | {sys.executable} -m piper --data-dir {tts_data_dir} --download-dir {tts_data_dir} --model {tts_model} --output_file {tts_data_dir}/test.wav', stdout=subprocess.PIPE, shell=True)
					subprocess.call(f'aplay {tts_data_dir}/test.wav', stdout=subprocess.PIPE, shell=True)
