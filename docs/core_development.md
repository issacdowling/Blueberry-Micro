# Core Development

## What Bloob needs from you

### Structure
You must create a file - either within your configuration directory's core folder (typically `~/.config/bloob/cores`, though this may not exist by default), or the repo directly if you plan to upstream it (at `src/cores/`) - that somehow includes the text `bb_core` in its name, as this is how Blueberry knows which files to run when searching for cores.

This also means that Python scripts (or any other interpreted language) should begin with a shebang, so that they can be executed regularly. E.g: `#!/bin/env python3` (`/bin/env python3` instead of `/usr/bin/python3` ensures that venvs work fine).

Your Cores must also be marked executable.

### Identification
If your core is launched with the argument `--identify true`, it must not run regularly, and will hold back the Orchestrator until it's completed identifying itself. Over stdout, it must return its Core ID (a string that uniquely identifies this core) and its roles (whether it provides Collections, Intents, etc).

An example snippet of this from the WLED core in python:
```python
core_id = "wled"

if arguments.identify:
  print(json.dumps({"id": core_id, "roles": ["intent_handler"]}))
  exit()
```

The current available roles are:

* `intent_handler`
* `collection_handler`
* `util`
* `no_config`

#### Intent Handler
An Intent Handler will provide intents (the format for which is described later on), which are events than can be called using the user's voice.

#### Collection Handler
A Collection Handler will provide Collections, which are groups of words that can be useful when detecting certain categories within the user's speech, and used within Intents.

#### Util
A Util represents something that isn't directly called by the user's speech, but completes a task involved in processing it or doing other operations related to it (for example, speech-to-text)

#### No Config
If you just want to build a super simple Core (any arbitrary program you want to launch with Bloob, but not to interact with voice, nor do you want to provide metadata), you can add this role, and a config will automatically be provided on your behalf, just containing the `core_id` (you still need to `identify`, so the main value is avoiding needing MQTT if you won't use it.)

### Core Config

I will explain Core configs using this example from the WLED core, though some features shown below aren't visible in this config.

```python
core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "WLED Device Handler",
    "link": "https://gitlab.com/issacdowling/blueberry-micro/-/tree/main/src/cores/wled",
    "author": "Issac Dowling",
    "icon": None,
    "description": "Allows setting / getting the basic states of WLED lights using their REST API",
    "version": "0.1",
    "license": "AGPLv3",
    "example_config": {
      "devices": [
        {
          "names": [
            "first device name",
            "other alias for device",
            "the first name is what will be used by bloob normally",
            "but you can say any of these and it'll work"
          ],
          "ip": "192.168.x.x"
        },
        {
          "names": [
            "I am a second device",
            "kitchen light"
          ],
          "ip": "172.30.x.x"
        }
      ]
    }
  },
  "intents": [{
    "id" : "setWLED",
    "core_id": core_id,
    "keywords": [all_device_names],
    "collections": [["set"], ["boolean", "colours", "any_number"]]
  }]
}
```

#### Metadata

**The `metadata` object is fairly self explanatory.**

* `core_id` is the ID of your core used to access it within bloob / MQTT, which - if you feel like following convention - should be in snake_case, and contain only alphanumeric characters/underscores
* `friendly_name` is the name that should appear to user-facing UIs, and can include spaces and a wider range of characters (though generally you should stick to what's "normal", just incase)
* `link` is a link to the Core's project online, typically expected to be a Git repo. This is optional, and can be None to be skipped
* `author` is your author name, treat its requirements similarly to `friendly_name`, though it is optional, but recommended
* `icon` is a base64 string of a PNG or SVG... with no official requirements for size, so I'll say keep the PNGs below 128x128, but realistically they could be 32x32 or 16x16 just fine. Be reasonable! This is highly optional
* `description` is a single/few sentence description of your core, and is optional though highly suggested
* `version` is your Core's version. Optional but suggested
* `license` is your Core's license. It is _literally_ optional, nothing should break if you don't add it, but ***YOU SHOULD ADD A LICENSE, EVEN IF IT'S JUST "Proprietary", SO PEOPLE KNOW WHAT THEY CAN/CAN'T DO WITH YOUR CODE!***

#### Intents

**The `intents` object is a list of Intents.**

*But what's an Intent?*

* `id` is like `core_id` but for your intent
* `core_id` is the `core_id` of the Core that's registering this intent, as it's how we know who to send the info to once we've parsed it.
* `keywords` must be a two-dimensional list; there's a first list which wraps your lists of keywords, and an arbitrary number of lists within. Each list within will be checked, and must contain at least one match. For example, `[["test"]]` will be matched by the intent parser if `"test"` is in your speech. `[["test", "hi"]]` will be matched if EITHER `"test"` or `"hi"` is in your speech. `[["test"], ["hi"]]` will be matched if `"test"` AND `"hi"` are in your speech. Everything within each list should just be a string of alphanumeric characters (I filter the input, and any special characters from the STT are stripped), and one that you expect that the user would say to call your Core. Adding common false positives (like "dolite" for "door light", in my case") may help.
* `collections` has a very similar format to `keywords`, however the strings are referencing the name of Collections. Otherwise, the checking logic is identical, so you can learn more about this in the Collections section.
* `prefixes` allows you to specify a string that the user's speech must begin with in order for your Core to be selected. Unlike with Keywords, where requesting "test" wouldn't match with "tests" (in other words, we're checking for full words), the prefix option just checks for the string (so, "test" would match the user starting with "tests"). This is a single list, and any string within that list matching will cause this section to pass. For example: `prefixes: ["test", "other thing"]` would activate if I said "test this thing", "other thing needs testing", or "tests are cool", but not if I said "this is a test", or "i need one more other thing"
* `suffixes` is exactly the same as `prefixes`, except looking for a string at the _end_ of the user's speech.