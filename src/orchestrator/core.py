""" Core class for the Orchestrator """
import logging
import subprocess
import json
class Core:
    def __init__(self, path, mqtt, devid="test"):
        if devid == None:
            exit("No device_id in config")
        self.mqttserver = mqtt
        self.path = path
        self.devid = devid
        logging.debug(f"Readying core at: {self.path}")

        # Get core identification
        core_run = subprocess.run([self.path, "IDENTIFY"],capture_output=True)
        try:
            self.core_json = json.loads(core_run.stdout.decode())
        except:
            debug.error(f"Unable to load core at {self.path}")
            return
        print(self.core_json)
        self.name = self.core_json.get("name")
        self.friendly_name = self.core_json.get("friendly_name")
        self.is_device_handler = bool(self.core_json.get("device_handler"))

        if(self.is_device_handler):
            logging.info(f"Device Handler {self.friendly_name} loaded.")
        else:
            logging.info(f"Core {self.friendly_name} loaded.")
    
    def construct_run_args(self):
        args = [self.path]
        if(self.mqttserver.host != None):
            args.append("--host")
            args.append(self.mqttserver.host)
        if(self.mqttserver.port != None):
            args.append("--port")
            args.append(str(self.mqttserver.port))
        if(self.mqttserver.user != None):
            args.append("--user")
            args.append(self.mqttserver.user)
        if(self.mqttserver.password != None):
            args.append("--pass")
            args.append(self.mqttserver.password)
        args.append("--device-id")
        args.append(self.devid)
        
        return args

    def run(self):
        self.running_core = subprocess.Popen(self.construct_run_args(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def stop(self):
        self.running_core.terminate()
