# MQTT API

**All requests related to Blueberry will begin with `bloob/`, and - though there may potentially be some device-agnostic topics in the future - this is currently also always followed by your `device-id` (`bloob/device-id/`)**

**What needs to go in field `x`?** Check the `Formats` section for info on this

## Logging

Topic: **`bloob/<device-id>/logs`**

Example Output:
```
[tts] Generating speech
```

* **What:** Logs from all bloob-related things will appear here, along with the program they came from
* **Why:** Logs are helpful.
* **Notes:**
	* The entirety of the log is generated by the program sending it, meaning technically any program could impersonate any other (though, realistically, I don't forsee this being a real risk)
	* This is just plaintext, no JSON here (though, you _could_ include it as an extra part, but generally these are just text)
	* These are quite verbose sometimes, with no log levels, however that's the way I want it

## Listening/Thinking

Topic: **`bloob/<device-id>/recording`**

Example Output:
```
{"is_recording": True}
```

* **What:** Reports `is_recording` as True while recording audio, False while not.
* **Why:** External programs may want to represent whether the assistant is listening/computing a response, and this is a simpler (and more securable) way of doing that than directly accessing the audio recorder / other steps of completing the request.
* **Notes:**
	* Though typically you might call this "listening" (and clients are welcome to do so), I've chosen to name this topic "recording" since "listening" may be reserved for representing whether the mic is muted or not.

Topic: **`bloob/<device-id>/thinking`**

Example Output:
```
{"is_thinking": True}
```

* **What:** Reports `is_thinking` as True while computing the response to your query, False while not.
* **Why:** See the previous example.
* **Notes:**
	* This becomes `False` just before actual speaking begins.

## List Running Cores

Topic: **`bloob/<device-id>/cores/list`**

Example Output:
```
{"loaded_cores": ["date_time_get", "wled"]}
```

* **What:** Publishes a list of cores that the Orchestrator has loaded
* **When:** Currently, this is published to upon startup of the Orchestrator, and retained
* **Notes:** 
	* In the future, it may change during runtime if Cores being dynamically loaded is deemed a feature worth making

## Centralised Configs

Topic: **`bloob/<device-id>/cores/<core-id>/central_config`**

Example Output:
```
{"devices": [{"names": ["light", "LED"], "ip": "x.x.x.x"}, {"names": ["other light", "other LED"], "ip": "x.x.x.x"}]}
```

* **What:** Publishes the value of the key in the main `config.json` matching the `core-id`
* **Why:** Cores may find it valuable for all non-sensitive configuration to be done in a central place
* **When:** Currently, this is published to upon startup of the Orchestrator, and retained
* **Notes:**
	* In the future, it may change during runtime if Cores being dynamically loaded is deemed a feature worth making
	* You're putting these configs in a shared file, and sending them over MQTT. You may choose to deal with sensitive information (such as precise location) in a more secure way. This is a convenience feature.
	* Pay no real attention to the example output for this topic, it's the WLED config, and could be any JSON object.

## Core Configs

Topic: **`bloob/<device-id>/cores/<core-id>/config`**

Example Output:
```
{"metadata": {"core_id": "date_time_get", "friendly_name": "Date / Time Getter", "link": null, "author": null, "icon": null, "description": null, "version": 0.1, "license": "AGPLv3"}, "intents": [{"id": "getDate", "keyphrases": ["date", "day", "time"], "type": "get", "core_id": "date_time_get", "private": true}]}
```

* **What:** Publishes the configuration that the Core chooses to report back to us. This is not for configuring the core itself, but for letting us know information about the Core, such as metadata and its exposed Intents
* **When:** Currently, this is published to upon startup of the Core, and retained

## Registering Intents

Topic: **`bloob/<device-id>/cores/<core-id>/intents/<intent-id>`**

Example Input:
```
{ "id" : "setWLEDBoolOrColour", "core_id": core_id, "keyphrases": [["$set"], all_device_names, ["$boolean", "$colours"]] }
```

* **What:** For every Intent that your Core wants to expose (if any), it should publish them here. They'll be picked up by the Intent Parser asynchronously (you can do this whenever, and it'll still do it, not just on startup). Send whole JSON objects.

## Registering Collections

Topic: **`bloob/<device-id>/collections/<collection-id>`**

Example Input:
```
{	"id": "get", "keyphrases": ["get", "what", "whats", "is", "tell me" ] }
```

* **What:** As with Intents, this is asynchronous, and allows you to register Collections. Send whole JSON objects.

## Wakeword detected

Topic: **`bloob/<device-id>/cores/wakeword_util/finished`**

Example Output:
```
{"wakeword_id": "hello", "confidence": "0.96480765"}
```

* **What:** Publishes the name of the wakeword detected, and the confidence
* **When:** Any time a wakeword is detected

## Audio Playback

### Whole File

Topic: **`bloob/<device-id>/cores/audio_playback_util/play_file`**

Example Input:
```
{"id": "1640", "audio": "H4sIAKo3CWYC/wvPqFRIyUxRqMwvVUhJTc7PLShKLS5WKMnILFaws9JQAADTSskbIAAAAA=="}
```

* **What:** Publish audio to this topic, and the `audio_playback` util will play it back in its entirety

### Finished
Topic: **`bloob/<device-id>/cores/audio_playback_util/finished`**

Example Output:
```
{"id": "1640"}
```

* **What:** Notifies that audio playback has completed
* **When:** Whenever audio is done playing

## Audio Recording

### Speech
Topic: **`bloob/<device-id>/cores/audio_recorder_util/record_speech`**

Example Input:
```
{"id": "1640"}
```

* **What:** Tells the `audio_recorder` to begin recording, and stop once speech is no longer being detected

### Finished
Topic: **`bloob/<device-id>/cores/audio_recorder_util/finished`**

Example Output:
```
{"id": "1640", "audio": "H4sIAP85CWYC/wvJyCxWyCzOUy9RSC1LzVNIMjPRAwBB5uVyFAAAAA=="}
```

* **What:** Outputs the recorded audio
* **When:** Whenever audio is finished being recorded.

## Transcription

### Transcribe
Topic: **`bloob/<device-id>/cores/stt_util/transcribe`**

Example Input:
```
{"id": "1640", "audio": "H4sIAPA8CWYC//swv2+rgl9qWWqRQnp+Xl6iQnpmWapCZX6pQmmBwgegJAAJP45LIQAAAA=="}
```

* **What:** Tells the `stt` to transcribe your audio

### Finished
Topic: **`bloob/<device-id>/cores/stt_util/finished`**

Example Output:
```
{"id": "1640", "text": " What time is it?"}
```

* **What:** Outputs the transcribed text
* **When:** Whenever audio is finished being transcribed.

## Intent Parsing

### Parse
Topic: **`bloob/<device-id>/cores/intent_parser_util/run`**

Example Input:
```
{"id": "1640", "text": " What time is it?"}
```

* **What:** Tells the `intent_parser` to provide you with the understood intent of the text.
* **Notes:**
	* If building your own things ontop of this, you may find it more efficient (at least, unless this spec changes) to directly send the output of `stt`, as it matches the expected input here
	* May in the future provide options for on-the-fly, ephemeral additions of intents for individual requests
	* The intent parser learns of intents through subscribing to all cores in the `loaded_cores` key mentioned in the `List Cores` section earlier, and checking them in the received config

### Finished
Topic: **`bloob/<device-id>/cores/intent_parser_util/finished`**

Example Output:
```
{"id": "1640", "intent": "getDate", "core_id": "date_time_get", "text": "what time is it"}
```

* **What:** Outputs the understood intent
* **When:** Whenever intents are finished being parsed.
* **Notes:**
	* Outputs, and uses internally, a cleaned up version of the text, with symbols removed or swapped for words (`%` for `"percent"`), and all lowercase

## Core Running
### Run
Topic: **`bloob/<device-id>/cores/<core-id>/run`**

Example Input:
```
{"id": "1640", "intent": "getDate", "text": "what time is it"}
```

* **What:** Tells the Core to run the given intent, and provides the transcribed and cleaned up text that was parsed

### Finished
Topic: **`bloob/<device-id>/cores/<core-id>/finished`**

Example Output:
```
{"id": "1640", "text": "The time is 11:09 PM", "explanation": "Got that the current time is 11:09 PM"}
```

* **What:** Outputs the core's intended speech, an explanation of what was done (for future use), and whether to end the conversation or continue
* **When:** Whenever the core is finished running
* **Notes:**
	* `"text"` is the default, suggested speech to output
	* `"explanation"` is mostly similar, but maybe more verbose and less colloquial. Potentially useful in the future in combination with LLMs, so it's already part of the spec despite not currently being in use, as it's not hard to implement.
	* `"end_type"` can either be `"finish"` - which is the default, and means that we're done with this core - or `"converse"`, which means that it would like some TTS input for further processing. The rest of this is not yet implemented, however I expect to run TTS, then - rather than rely on the core for state - provide the core with previous input and current conversational additions, to allow back-and-forth conversation

## TTS
### Run
Topic: **`bloob/<device-id>/cores/tts_util/run`**

Example Input:
```
{"id": "1640", "text": "The time is 11:09 PM"}
```

* **What:** Tells the `tts` to speak the given text

### Finished
Topic: **`bloob/<device-id>/cores/tts_util/finished`**

Example Output:
```
{"id": "1640", "audio": "H4sIADZFCWYC//NUSMnPe9Qws0QhJzM7VaE4MS9FT8GzBChSrJCcn1hUnKoAFFIoyi9NzwCzMouKMksSSzLz0nUg/BKF9NSSYoXUstSiyvKM1KJUPQDDT8QmVAAAAA=="}
```

* **What:** Outputs the audio of the request's requested speech being spoken
* **When:** Whenever TTS finishes speaking




## Formats

### ID
* Check that the ID matches your input request to make sure you're dealing with _your_ request
* Can be any string

### Audio
* The audio is a base64 encoded WAV string. 
* If you're struggling with this, here's an example of creating the correct format in Python:
```python
import base64
with open("test.wav", 'rb') as wf:
	string_audio_to_send = base64.b64encode(wf.read()).decode()
```
* We're taking that WAV, reading it, which is passed into the `b64encode` function, which produces a `bytes` object, which we then `decode()` into a `string`
* Here's an example of turning this back into a WAV file in Python:
```python
import base64
with open("test.wav",'wb+') as audio_file:
	audio_file.write(base64.b64decode(received_audio_str.encode()))
```
* We're taking that `str`, `encode()`-ing it back into bytes, which is passed into the `b64decode` function, which produces the original `bytes` that can be written back to a file





