# Blueberry

![The Blueberry Logo](resources/favicon.svg)

## Blueberry is a selfhostable, FOSS, and hackable voice assistant.

The aim of this project is to make it easier for developers to develop voice-controlled things using any language they wish, and for users to have a privacy-respecting and offline-capable voice assistant that's still perfectly usable.

The idea came from my past use of [Rhasspy](https://github.com/rhasspy/rhasspy), but the concern that I didn't understand the codebase, and therefore had no idea how to extend it to my needs (along with wanting a challenge that would teach me new things.) 

## The stack

Communication is handled by MQTT (I use [Mosquitto](https://mosquitto.org/)), as this allows for everything to be highly modular, and for easy integration with existing smart-home systems.

Speech-To-Text is handled by a _local instance_ of [OpenAI Whisper](https://github.com/openai/whisper) (specifically, [faster-whisper](https://github.com/SYSTRAN/faster-whisper)). You can customise the size of the model to find the ideal compute/accuracy tradeoff for your hardware.

Text-To-Speech is handled by [Piper](https://github.com/rhasspy/piper), a very fast and decent-sounding (depending on the individual model) TTS system that's also completely local.

Wakewords / Instant Intents are handled by [OpenWakeWord](https://github.com/dscripka/openWakeWord), which is also completely local, and provides numerous existing trained wakewords, along with the potential for making your own.

Intent Parsing is handled by custom code that intends to allow understanding of quite varied speech, while providing the tools for developers to create Cores easily.