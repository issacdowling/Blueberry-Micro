# Core Development

## What Bloob needs from you

### Core Config

I will explain Core configs using this example from the WLED core:

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
    "license": "AGPLv3"
  },
  "intents": [{
    "intent_id" : "setWLED",
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

* `intent_id` is like `core_id` but for your intent
* `core_id` is the `core_id` of the Core that's registering this intent, as it's how we know who to send the info to once we've parsed it.
* `keywords` must be a two-dimensional list; there's a first list which wraps your lists of keywords, and an arbitrary number of lists within. Each list within will be checked, and must contain at least one match. For example, `[["test"]]` will be matched by the intent parser if `"test"` is in your speech. `[["test", "hi"]]` will be matched if EITHER `"test"` or `"hi"` is in your speech. `[["test"], ["hi"]]` will be matched if `"test"` AND `"hi"` are in your speech. Everything within each list should just be a string of alphanumeric characters (I filter the input, and any special characters from the STT are stripped), and one that you expect that the user would say to call your Core. Adding common false positives (like "dolite" for "door light", in my case") may help.
* `collections` has a very similar format to `keywords`, however the strings are referencing the name of Collections. Otherwise, the checking logic is identical, so you can learn more about this in the Collections section.

### Collections
TBD