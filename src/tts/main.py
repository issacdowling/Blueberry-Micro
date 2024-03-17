""" MQTT connected TTS engine for Blueberry, making use of Piper TTS """
import argparse
import subprocess
import asyncio
import aiomqtt
import sys
import re
import json
import base64

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host')
arg_parser.add_argument('--port')
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass')
arg_parser.add_argument('--device-id')
arg_parser.add_argument('--tts-path')
arg_parser.add_argument('--tts-model')
arguments = arg_parser.parse_args()

def speak(text):
    speech_text = re.sub(r"^\W+|\W+$",'', text)
    tts_path = arguments.tts_path
    tts_model_path = f"{tts_path}/{arguments.tts_model}.onnx"
    output_audio_path = f"{tts_path}/out.wav"
    subprocess.call(f'echo "{speech_text}" | {sys.executable} -m piper --data-dir {tts_path} --download-dir {tts_path} --model {tts_model_path} --output_file {output_audio_path}', stdout=subprocess.PIPE, shell=True)
    print("run")
    
    

async def connect():
    async with aiomqtt.Client(arguments.host) as client:
        await client.subscribe(f"bloob/{arguments.device_id}/tts/run")
        async for message in client.messages:
            try:
                message_payload = json.loads(message.payload.decode())
                if(message_payload.get('text') != None and message_payload.get('id') != None):
                    speak(message_payload.get('text'))
                    # encode speech to base64
                    with open(f"{arguments.tts_path}/out.wav", 'rb') as f:
                        encoded = base64.b64encode(f.read())
                        str_encoded = encoded.decode()
                    await client.publish(f"bloob/{arguments.device_id}/tts/finished", json.dumps({"id": message_payload.get('id'), "speech":str_encoded}))
            except:
                print("Error with payload.")

asyncio.run(connect())
