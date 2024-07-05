#!/bin/env python3
""" Core that communicates with the Timer-Sync daemon to provide networked timer sync for Bloob """
# load modules
import aiomqtt
import asyncio
import argparse
import signal
import paho, paho.mqtt, paho.mqtt.publish
import sys
import pathlib
import json
import subprocess
import mpv

import pybloob

core_id = "sync_clock"

arguments = pybloob.coreArgParse()
c = pybloob.Core(device_id=arguments.device_id, core_id=core_id, mqtt_host=arguments.host, mqtt_port=arguments.port, mqtt_user=arguments.user, mqtt_pass=arguments.__dict__.get("pass"))

# define the core config
core_config = {
    "metadata": {
        "core_id": core_id,
        "friendly_name": "Timer sync daemon client",
        "link": "https://gitlab.com/issacdowling/sync-clock",
        "author": "ConfusionUnknown",
        "icon": None,
        "description": "Allows communication with the Timer-Sync daemon, providing networked timers for Blueberry",
        "version": "0.1",
        "license": "AGPLv3"
    }
}

intents = [
        {
            "id": "setTimer",
            "core_id": core_id,
            "keyphrases": [ ["set", "make", "create"], ["timer", "counter"], ["minutes", "minute", "seconds", "second", "hour", "hours"] ],
            "numbers": {"any": "any"}
        },
        {
            "id": "stopTimer",
            "core_id": core_id,
            "keyphrases": [ ["stop", "cancel", "dismiss"], ["timer"] ]
        },
        {
            "id": "getTimer",
            "core_id": core_id,
            "keyphrases": [["$get"], ["timer", "counter"], ["remaining", "left"] ],
        }
    ]

async def main():
    global daemon_proc, log_data, mpv_player
    # get logging working
    log_data = arguments.host, int(arguments.port), arguments.device_id, core_id
    c.log("Starting daemon")
    # start the daemon
    daemon_dir = pathlib.Path(sys.argv[0]).parent.joinpath("daemon")
    daemon = daemon_dir.joinpath("main.py")
    daemon_proc = subprocess.Popen([sys.executable, daemon], stdin=None, stdout=None, stderr=None)
    c.log("Daemon running")
    # get mpv ready
    mpv_player = mpv.MPV()
    # create sounding loop
    asyncio.create_task(sounder())
    async with aiomqtt.Client(hostname=arguments.host, port=int(arguments.port), username=arguments.user, password=arguments.__dict__.get("pass")) as client:
        # sub to intent topic
        await client.subscribe(f"bloob/{arguments.device_id}/cores/{core_id}/run")
        # sub to timer topcis
        await client.subscribe("bloob/timers/finish")
        await client.subscribe("bloob/timers/dismissed")
        await client.subscribe("bloob/timers/status")

        # publish core config
        await client.publish(f"bloob/{arguments.device_id}/cores/{core_id}/config", payload=json.dumps(core_config), retain=True, qos=1)
        c.log("Core config published")

        for intent in intents:
            await client.publish(f"bloob/{arguments.device_id}/cores/{core_id}/intents/{intent['id']}", payload=json.dumps(intent), retain=True, qos=1)

        # enter message handle loop
        async for message in client.messages:
            try:
                await handle_message(message, client)
            except Exception as e:
                c.log(f"Unable to parse message. ({e})")
sounding = False
timer_status = []
async def handle_message(message, client):
    global sounding, timer_status
    message_decoded = json.loads(message.payload.decode())
    if(message.topic.matches(f"bloob/{arguments.device_id}/cores/{core_id}/run")):
        match message_decoded["intent"]:
            case "setTimer":
                # find the amount of time
                amount_of_time_number = 0
                for word in message_decoded["text"].split(" "):
                    if word.isnumeric():
                        amount_of_time_number = int(word)
                        break
                # find the unit
                seconds = amount_of_time_number
                hours = ["hour", "hours"]
                minutes = ["minute", "minutes"]
                if(pybloob.getTextMatches(match_item=hours, check_string=message_decoded["text"])):
                    seconds = seconds * 600
                    time_unit = "hour"
                elif(pybloob.getTextMatches(match_item=minutes, check_string=message_decoded["text"])):
                    seconds = seconds * 60
                    time_unit = "minute"
                else:
                    time_unit = "second"

                c.log(f"Found time as {seconds} seconds.")

                # start the timer!
                await client.publish("bloob/timers/start", payload=json.dumps({
                    "length": seconds,
                    "source": {
                        "name": "Voice",
                        "uuid": arguments.device_id
                    }
                                                                               }))

                # respond to the intent
                spoken = f"Sure thing, I'll start a {amount_of_time_number} {time_unit} timer"
                explanation = f"The timer core started a timer with length {seconds} seconds ({amount_of_time_number} {time_unit})."
                # avoid race condition in the bloob orchestrator, wait slightly
                await asyncio.sleep(0.01)
                await client.publish(f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({
                    "id": message_decoded["id"],
                    "text": spoken,
                    "explanation": explanation,
                    "end_type": "finish"
                }))
            case "stopTimer":
                await client.publish(f"bloob/timers/stop", payload=json.dumps({}))
                spoken = "Alright, I'll stop the timer"
                explanation = f"The timer core stopped the timer that was going off."
                # avoid race condition in the bloob orchestrator, wait slightly
                await asyncio.sleep(0.01)
                await client.publish(f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({
                    "id": message_decoded["id"],
                    "text": spoken,
                    "explanation": explanation,
                    "end_type": "finish"
                }))
            case "getTimer":
                if(len(timer_status) > 0):
                    # there is an active timer
                    # convert to nice human readable numbers
                    hours = 0
                    minutes = 0
                    seconds = int(timer_status[0]["length"])
                    spoken = "You have "
                    # get hours, if any
                    if(seconds >= 3600):
                        while seconds >= 3600:
                            seconds -= 3600
                            hours += 1

                        spoken += f"{hours} hours, "
                    # get minutes, if any
                    if(seconds >= 60):
                        while seconds >= 60:
                            seconds -= 60
                            minutes +=1
                        spoken += f"{minutes} minutes, "
                    # add seconds to string, if not zero
                    if(seconds >= 0):
                        spoken += f"{seconds} seconds"
                    spoken += " remaining on your timer"
                    explanation = f"The timer core checked for running timers, and the amount of time left on the timer was {hours} hours, {minutes} minutes, {seconds} seconds."
                else:
                    # no active timer
                    spoken = "You don't have any running timers right now."
                    explanation = "The timer core checked for running timers and there were no active timers."
                # avoid race condition in the bloob orchestrator, wait slightly
                await asyncio.sleep(0.01)
                await client.publish(f"bloob/{arguments.device_id}/cores/{core_id}/finished", payload=json.dumps({
                        "id": message_decoded["id"],
                        "text": spoken,
                        "explanation": explanation,
                        "end_type": "finish"
                    }))
    if(message.topic.matches(f"bloob/timers/finish")):
        # play boop sound
        sounding = True
    if(message.topic.matches(f"bloob/timers/dismissed")):
        # stop sounding
        sounding = False
    if(message.topic.matches(f"bloob/timers/status")):
        timer_status = message_decoded

async def sounder():
    global mpv_player, sounding
    while True:
        if(sounding):
            c.log("Sounding")
            timer_sound = str(pathlib.Path(sys.argv[0]).parent.joinpath("timer.wav"))
            mpv_player.play(timer_sound)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
