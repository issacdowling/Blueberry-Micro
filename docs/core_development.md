# Core Development

## What Bloob needs from you

### Structure
You must create a file - either within your configuration directory's core folder (typically `~/.config/bloob/cores`, though this may not exist by default), or the repo directly if you plan to upstream it (at `src/cores/`) - that somehow includes the text `bb_core` in its name, as this is how Blueberry knows which files to run when searching for cores.

This also means that Python scripts (or any other interpreted language) should begin with a shebang, so that they can be executed regularly. E.g: `#!/bin/env python3` (`/bin/env python3` instead of `/usr/bin/python3` ensures that venvs work fine).

Your Cores must also be marked executable.

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
  }
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



## Intents

```python
intents = [
  {
  "id" : "setWLEDBoolOrColour",
  "core_id": core_id,
  "keyphrases": [["$set"], all_device_names, ["$boolean", "$colours"]]
  },
  {
  "id" : "setWLEDBrightness",
  "core_id": core_id,
  "keyphrases": [["$set"], all_device_names],
  "numbers": {"any": "any"}
  }
]
```

*What's an Intent?*

* `id` is like `core_id` but for your intent
* `core_id` is the `core_id` of the Core that's registering this intent, as it's how we know who to send the info to once we've parsed it.
* `keyphrases` must be a two-dimensional list; there's a first list which wraps your lists of keyphrases, and an arbitrary number of lists within. Each list within will be checked, and must contain at least one match. For example, `[["test"]]` will be matched by the intent parser if `"test"` is in your speech. `[["test", "hi"]]` will be matched if EITHER `"test"` or `"hi"` is in your speech. `[["test"], ["hi"]]` will be matched if `"test"` AND `"hi"` are in your speech. Everything within each list should just be a string of alphanumeric characters (I filter the input, and any special characters from the STT are stripped), and one that you expect that the user would say to call your Core. Adding common false positives (like "dolite" for "door light", in my case") may help. You can also use keyphrases from a Collection by referring to them using `$name` in your keyphrase lists. Every keyphrase in this Collection will be added to the list that you put this value in.
* `adv_keyphrases` is an alternative to `keyphrases` (though they can be used in the same Intent if you wish). It detects the words that you specify, and allows you to substitute them for something else _before_ passing along to your Core. They follow this format (ignore the irrelevant words): `[{"hello there": "hi", "morning": ""}, {"good evening": "", "car": "automobile"}]`. As with regular `keyphrases`, we wrap everything in a list but inside - instead of more lists - there are objects. At least one key from within this object must be found in your text for these checks to pass, which we already know. What's new is that if I said `"hello there"` in my text, it would be replaced with `"hi"`, but if I said `"morning"`, it would still be detected, yet not replaced since the value is an empty string (`""`). They support Collections just as `keyphrases` does - as the key - except a blank value will leave substitutions up to the Collection, and a custom value will substitute that value in for every detection of something within that Collection.
* `prefixes` allows you to specify a string that the user's speech must begin with in order for your Core to be selected. Unlike with keyphrases, where requesting "test" wouldn't match with "tests" (in other words, we're checking for full words), the prefix option just checks for the string (so, "test" would match the user starting with "tests"). This is a single list, and any string within that list matching will cause this section to pass. For example: `prefixes: ["test", "other thing"]` would activate if I said "test this thing", "other thing needs testing", or "tests are cool", but not if I said "this is a test", or "i need one more other thing"
* `suffixes` is exactly the same as `prefixes`, except looking for a string at the _end_ of the user's speech.

