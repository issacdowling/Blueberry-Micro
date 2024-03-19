""" The Orchestrator. Part of Blueberry """
import asyncio
import aiomqtt
import sys
import logging
import core
import mqttserver
import argparse
import os
import pathlib
import json
import webserver
import webserver.server

# Arguments
parser = argparse.ArgumentParser()
parser.add_argument('--data-dir', default=None)
arguments = parser.parse_args()
# Get the logging set up
logging.basicConfig(level=logging.DEBUG)

logging.addLevelName( logging.DEBUG, "\033[96m%s\033[1;0m" % logging.getLevelName(logging.DEBUG))
logging.addLevelName( logging.INFO, "\033[92m%s\033[1;0m" % logging.getLevelName(logging.INFO))
logging.addLevelName( logging.WARNING, "\033[93m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName( logging.ERROR, "\033[91m%s\033[1;0m" % logging.getLevelName(logging.ERROR))
logging.addLevelName( logging.CRITICAL, "\033[91m%s\033[1;0m" % logging.getLevelName(logging.CRITICAL))

logging.info("Orchestrator starting up.")

async def main():
    # Get the data dir sorted
    if(arguments.data_dir == None):
        data_dir = pathlib.Path(os.environ["HOME"]).joinpath(".config/bloob")
    else:
        data_dir = pathlib.Path(arguments.data_dir)
    logging.debug(f"using {data_dir} for data")
    cores_dir = data_dir.joinpath("cores")
    if (not data_dir.exists()):
        logging.info("Creating data directory.")
        os.mkdir(data_dir)
    if (not cores_dir.exists()):
        logging.info("Creating cores directory.")
        os.mkdir(cores_dir)
    # Load the configuration file
    try:
        with open(data_dir.joinpath("config.json"),"r") as f:
            config = json.load(f)
    except json.decoder.JSONDecodeError:
        logging.critical("Configuration parse failed, invalid JSON. Exiting.")
        exit(0)
    # Prepare the MQTT configuration
    json_config_mqtt = config.get("mqtt")
    mqtt_config = mqttserver.MQTTServer(host=json_config_mqtt.get("host"), port=json_config_mqtt.get("port"), user=json_config_mqtt.get("user"), password=json_config_mqtt.get("password"))
    # Then, ready all the cores
    logging.debug(f"Using {cores_dir} for cores")
    loaded_cores = []
    core_files = [str(core) for core in cores_dir.glob('*bb_core*')]
    for core_file in core_files:
        loaded_cores.append(core.Core(path=core_file,mqtt=mqtt_config, devid=config.get("device_id")))
    # Now, start all the cores
    for core_object in loaded_cores:
        core_object.run()
    # Run the webserver
    httpserver = webserver.server.OrchestratorHTTPServer(config)
    
    await httpserver.run_server()
    # Enter loop
    try:
        while True:
            await asyncio.sleep(1)
    except:
        # Time to stop
        logging.info("Shutting down.")
        for core_object in loaded_cores:
            core_object.stop()
            logging.info(f"Stopped core: {core_object.name}")
        logging.info("Stopping webserver")
        await httpserver.runner.cleanup()
    

if __name__ == "__main__":
    asyncio.run(main())
