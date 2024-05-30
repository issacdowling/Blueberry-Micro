# Blueberry Micro

# Setup

**If you're on Windows, just use WSL, this is not presently maintained for Windows.**

## Python
Presently, you need to use Python 3.11, due to `piper-tts` [issues](https://github.com/rhasspy/piper/issues/384).

I suggest that you create a virtual environment to keep the packages needed to make this work separate from the rest of your OS.

```
# First, change directory into this repo

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## MQTT
You'll need an MQTT broker to run bloob. The most common seems to be `mosquitto`

Arch: `sudo pacman -S moquitto`
Fedora: `sudo dnf install mosquitto`
Debian/Ubuntu: `sudo apt install mosquitto`
etc etc, it's `mosquitto` basically everywhere.

No configuration is necessary, however I expect to later find some configs that may be useful.

## Wakewords
While STT and TTS models can be downloaded automatically, Wakeword / Instant Intent words cannot, presently. Therefore, I suggest you go to the [OpenWakeWord Releases](https://github.com/dscripka/openWakeWord/releases/tag/v0.5.1) and download some models (specifically the ones ending in `.tflite`), which you'll put into `~/.config/bloob/ww/`. This directory is created automatically on first run (but remember, it won't pick up your voice without these models and a restart).

## Run:

This project needs you to build things yourself. Luckily, Go makes this easy.

Arch: `sudo pacman -S go`
Fedora: `sudo dnf install go`
Debian/Ubuntu: `sudo apt install golang`

Then, from the repo's root, you can just run:

```
source .venv/bin/activate
mosquitto -d
./run.sh
```
Which will activate the Python .venv, launch Mosquitto, and build/launch the Orchestrator.

If you'd rather build things yourself, or not build them on every launch, or any other situation where you want to launch things more manually (which, realistically, is most of the time), you can do your venv and MQTT stuff, build the Go things, then just run `.src/orchestrator/orchestrator`.

### Building

All you should need on your system is Golang.

```
cd src/orchestrator
go build -o orchestrator orchestrator.go mqtt.go utils.go cores.go

cd ../utils/intent_parser
go build -o intent_parser_util_bb_core intent_parser_util.go checks.go mqtt.go utils.go

cd ../../../
```

# Tips

## Logging!
You will NOT see all of the logs in the output of the Orchestrator's main.py (just the Orchestrator's logs). I've tried to ensure that this is enough information to broadly understand what's going on, but it may not be enough if you're trying to debug more major issues, so logging is handled over MQTT.

Each Bloob instance will log to `bloob/device-id/logs`, so subscribing to `bloob/+/logs` should get you all logs no matter what your device ID is set to. You can use something like `mosquitto_sub` for this (if debugging on your local machine, the command would be `mosquitto_sub -h localhost -t bloob/+/logs`), or you could download a GUI app like `MQTTX`.


## STT
Using a `large` Whisper model causes unusual and significant slowdowns just before transcription.
The default is distil-small (which is not the smallest), and this worked near-instantly for me, however I choose to use `Systran/faster-distil-whisper-medium.en` due to the higher quality transcription, though this may be unreasonably slow on less powerful machines.
You can use any Whisper model compatible with faster-whisper.