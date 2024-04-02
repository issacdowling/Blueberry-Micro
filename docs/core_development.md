# Core Development

## What Bloob needs from you

### Core Config

I will explain Core configs using this example from the WLED core:

```python
core_config = {
  "metadata": {
    "core_id": core_id,
    "friendly_name": "Date / Time Getter",
    "link": None,
    "author": None,
    "icon": None,
    "description": None,
    "version": 0.1,
    "license": "AGPLv3"
  },
  "intents": [{
    "intent_name" : "setWLED",
    "keywords": [all_device_names],
    "collections": [["boolean", "colours", "any_number"]],
    "core_id": core_id,
    "private": True
  }]
}
```