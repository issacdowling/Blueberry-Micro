#!/usr/bin/python3
import subprocess
import sys
from time import time

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
speech_buffer_length = 32000 # 2s of audio buffer at 16khz
vad_speech_margin_init = 16000 # The number of samples (normally 16000 for 1s) of "Not Speech" before the recording stops

vad_threshold = 0.1 #VAD set so low purely to prevent wasting time trying to understand silence. Tune manually if wanted.
vad_aggressiveness = 3 # 0-3, least to most aggressive at filtering noise

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
enabled_wakewords = ["weather"]

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

			print("Sending Audio")
			# TODO: Send to STT
			with wave.open('testoutput.wav', 'wb') as wf:
				wf.setnchannels(channels)
				wf.setsampwidth(audio_system.get_sample_size(paInt16))
				wf.setframerate(sample_rate)
				wf.writeframes(b''.join(speech_buffer))
			
			print("Waiting for wakeword:")


# TTS ########################################################

## Test TTS by speaking on launch
speech_text = "Blueberry is starting up"
tts_data_dir = "tts_data"
tts_model = f"{tts_data_dir}/en_US-lessac-high.onnx" # If this is a path, it will be loaded directly, but if it's just the name, it will redownload every time. https://github.com/rhasspy/piper to download.

subprocess.call(f'echo "{speech_text}" | {sys.executable} -m piper --data-dir {tts_data_dir} --download-dir {tts_data_dir} --model {tts_model} --output_file {tts_data_dir}/test.wav', stdout=subprocess.PIPE, shell=True)


#STT
stt_model = "base.en"