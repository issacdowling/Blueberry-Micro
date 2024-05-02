# Blueberry Micro

# Setup

**If you're on Windows, just use WSL, this is not presently maintained for Windows.**

## Python
Presently, you need to use Python 3.11, due to `piper-tts` [issues](https://github.com/rhasspy/piper/issues/384).

I suggest that you create a virtual environment to keep the packages needed to make this work separate from the rest of your OS.

```
# First, change directory into this repo

python -m venv .venv

pip install -r requirements.txt
```

## Wakewords
While STT and TTS models can be downloaded automatically, Wakeword / Instant Intent words cannot, presently. Therefore, I suggest you go to the [OpenWakeWord Releases](https://github.com/dscripka/openWakeWord/releases/tag/v0.5.1) and download some models (specifically the ones ending in `.tflite`), which you'll put into `~/.config/bloob/ww/`. This directory is created automatically on first run (but remember, it won't pick up your voice without these models and a restart).

# STT
Using a `large` Whisper model causes unusual and significant slowdowns just before transcription.
The default is distil-small (which is not the smallest), and this worked near-instantly for me.