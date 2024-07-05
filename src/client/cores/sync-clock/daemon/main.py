""" System for syncing timers and alarms across devices and smart speakers.
Background daemon for coordinating timers cross device.
"""
# load the modules
import aiomqtt
import argparse
import json
import asyncio
import message_handler
import logging

# pull in the arguments, mqtt server etc
arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--host', default="localhost")
arg_parser.add_argument('--port', default=1883)
arg_parser.add_argument('--user')
arg_parser.add_argument('--pass', dest="password")
arguments = arg_parser.parse_args()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
async def mqtt(timers):
    async with aiomqtt.Client(arguments.host, port=int(arguments.port), username=arguments.user, password=arguments.password) as cli:
        logger.info(f"Connected to MQTT broker at {arguments.host}:{arguments.port}")
        # subscribe
        await cli.subscribe("bloob/timers/stop")
        await cli.subscribe("bloob/timers/start")

        # instantiate message handler
        messagehandler = message_handler.MessageHandler(cli, timers)
        
        async with asyncio.TaskGroup() as tg:
            timer_task = tg.create_task(timer(timers, cli))
            listen_task = tg.create_task(listen(messagehandler, cli))

async def listen(messagehandler, client):
    logger.info("Listening for incoming message")
    async for message in client.messages:
        try:
            await messagehandler.handle_message(message)
        except:
            logger.critical("Error handling message.")

async def timer(timers, client):


    sounding = []
    logger.debug("Running timer loop")
    previous_timers = None
    await client.publish("bloob/timers/status", payload="[]", retain=True)
    while True:
        # subtract 1 from all timer lengths
        i = 0
        updated = False
        for timer in timers:
            updated_timer = timer
            if(timer["length"] > 0):
                updated_timer["length"] = timer["length"] - 1
                timers[i] = updated_timer
                updated = True
            else:
                # publish message on timer finish
                updated_timer["running"] = False
                timers[i] = updated_timer
                if(timer["id"] not in sounding):
                    sounding.append(timer["id"])
                    await client.publish("bloob/timers/finish", payload=json.dumps({"id": timer["id"]}))
                updated = True
        if updated:
            await client.publish("bloob/timers/status",payload=json.dumps(timers), retain=True)
        # clear list of published timer finish messages if the timer is removed
        # FIXME: This is a bad way to do this, and may cause issues at some point.
        if len(timers) == 0:
            sounding.clear()
#        logger.debug("Send")
        
        await asyncio.sleep(1)

async def main():
    timers = []

    await mqtt(timers)
if __name__ == "__main__":
    asyncio.run(main())
