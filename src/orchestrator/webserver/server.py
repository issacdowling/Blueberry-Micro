""" Webserver component of the Blueberry Orchestrator, responsible for the dashboard """
import asyncio
import aiohttp
import aiohttp.web
import logging
class OrchestratorHTTPServer:
    def __init__(self, config):
        self.config = config
        self.app = aiohttp.web.Application()
        self.app.add_routes([aiohttp.web.get('/',self.index)])
    async def index(self, request):
        return aiohttp.web.Response(text="<h1>orchestrator running</h1>", content_type="text/html")
    async def run_server(self):

        # Setup runner
        self.runner = aiohttp.web.AppRunner(self.app)
        await self.runner.setup()
        # get host and port
        if(self.config.get("http").get("host") == None):
            host = "localhost"
        else:
            host = self.config.get("http").get("host")
        if(self.config.get("http").get("port") == None):
            port = 8080
        else:
            port = int(self.config.get("http").get("port"))
        # Define the site
        self.site = aiohttp.web.TCPSite(self.runner, host, port)
        #Start
        await self.site.start()
        logging.info(f"HTTP Server running on {host}:{port}")

