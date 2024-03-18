""" MQTT Server class for the Orchestrator """
class MQTTServer:
    def __init__(self,host="localhost",port=1883,user=None,password=None):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
