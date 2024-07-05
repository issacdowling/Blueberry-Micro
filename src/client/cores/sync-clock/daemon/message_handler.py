""" Message handler, Part of the Bloob Timersync """
import asyncio
import json
import logging
class MessageHandler:
    def __init__(self, client, timers):
        self.client = client
        self.logger = logging.getLogger(__name__)
        self.timers = timers
    async def handle_message(self, message):
        try:
            decoded_payload = json.loads(message.payload.decode())

            if(message.topic.matches("bloob/timers/start")):
                #TODO: Figure out multiple timers, right now just don't start more than one
                if(len(self.timers) < 1):
                    self.timers.append({
                        "id": 1, "length": int(decoded_payload["length"]), "source": {
                            "name": decoded_payload["source"]["name"],
                            "uuid": decoded_payload["source"]["uuid"]
                        },
                        "running": True
                    })
            if(message.topic.matches("bloob/timers/stop")):
                for timer in self.timers:
                    self.timers.remove(timer)
                    await self.client.publish("bloob/timers/dismissed", payload=json.dumps({"id":timer["id"]}))
                    await self.client.publish("bloob/timers/status", payload=json.dumps(self.timers), retain = True)

        except:
            self.logger.warning("Unable to decode message.")
            
