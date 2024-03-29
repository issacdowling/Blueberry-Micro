""" Core class for the Orchestrator """
import logging
import subprocess
import json
class Core:
    def __init__(self, path, devid="test", host="localhost", port=1883, username=None, password=None):
        if devid == None:
            exit("No device_id in config")
        self.devid, self.host, self.port, self.username, self.password, self.path = devid, host, port, username, password, path
        
        # Get core identification
        core_run = subprocess.run([self.path, "--identify", "true"],capture_output=True)
        try:
            self.core_json = json.loads(core_run.stdout.decode())
        except AttributeError:
            logging.error(f"Unable to load core at {self.path} due to JSON issue")
            return
        self.core_id = self.core_json.get("id")
    
    def construct_run_args(self):
        args = [self.path]
        if(self.username != None):
            args.append("--user")
            args.append(self.username)
        if(self.password != None):
            args.append("--pass")
            args.append(self.password)
        args.append("--device-id")
        args.append(self.devid)
        
        return args

    def run(self):
        self.running_core = subprocess.Popen(self.construct_run_args(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def stop(self):
        self.running_core.terminate()
