#!/usr/bin/python3
import subprocess
import sys

## Test TTS by speaking on launch
speech_text = "Blueberry is starting up"
tts_data_dir = "tts_data"
tts_model = f"{tts_data_dir}/en_US-lessac-high.onnx" # If this is a path, it will be loaded directly, but if it's just the name, it will redownload every time. https://github.com/rhasspy/piper to download.

subprocess.call(f'echo "{speech_text}" | {sys.executable} -m piper --data-dir {tts_data_dir} --download-dir {tts_data_dir} --model {tts_model} --output_file {tts_data_dir}/test.wav', stdout=subprocess.PIPE, shell=True)


#STT
stt_model = "base.en"