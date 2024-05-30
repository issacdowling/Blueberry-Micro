# Config

* **The main config file is found, by default, at `~/.config/bloob/config.json`**
* **Sections mentioned here will contain key:value pairs, which can be added in any order (this is just regular JSON) to your `config.json`**
* **Default suggested values will be actual values (e.g `127.0.0.1`), example values where we can't guess what you might need will be clear (e.g `x.x.x.x` or `example-name`), values that can be empty contain `null`**
* **Other Cores can choose to have information stored in this main config file, simply by adding a key with the ID of the core, with the value of an object that will be sent to the core on startup of the Orchestrator. You can choose to configure your Core in any way you see fit, especially if security is a concern due to this being a shared file that'll be transmitted over the network, however it's likely the way to go for most usecases.**

## Instance ID (required)
```
"instance_name": "Default Name", "uuid": "123456789"
```

* `instance_name` is the friendly name of your instance, which can be changed
* `uuid` is the unique identifier of your instance, which should not be changed

## STT (required)
```
"stt": {
    "model": "Systran/faster-distil-whisper-small.en"
},
```

* `model` is the chosen Whisper model to use for STT purposes, and should be able to be entered into the `faster-whisper` Python library

## TTS (required)
```
"tts": {
    "model": "en_US-lessac-high"
},
```

* `model` is the chosen Piper model to use for TTS purposes

## MQTT (required)
```
"mqtt": {"host": "127.0.0.1", "port": 1883, "user": null, "password": null}
```

* `host` and `port` are the hostname and port of your MQTT broker
* `user` and `password` are the username and password to connect with
* `port` is an integer, not a string!

## Orchestrator
```
"orchestrator": {
    "show_remote_logs": true
    "external_cores": [
        {"id": "testcore1", "roles": ["intent_handler"]},
        {"id": "testcore2", "roles": ["no_config"]}
    ]
},
```

* `show_remote_logs` decides whether the Orchestrator's stdout should show all other bloob logs, as opposed to just its own.
* `external_cores` are Cores that the Orchestrator should know about (and therefore tell downstream services about them)
    * This is useful if you're running cores as daemons, or on other machines, or just launching them with any method that is not directly through the Orchestrator
    * They do not currently support being `collection_handler`s, due to some rearchitecting going on.
    * If these cores are not available, we can't know, and your Intent Parser will freeze up!