# Blueberry Micro

Presently, you need to use Python 3.11, due to `piper-tts` issues (https://github.com/rhasspy/piper/issues/384).

# STT
Using a `large` Whisper model causes unusual and significant slowdowns just before transcription.
The default is distil-small (which is not the smallest), and this worked near-instantly for me.