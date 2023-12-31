""" Configuration Server for Blueberry Voice Assistant """
import aiohttp.web
import aiohttp
import asyncio
import json

conf_file = {}
with open('config.json') as f:
    try:
        conf_file = json.loads(f.read())
    except:
        print("Unable to parse config.")
        exit(0)

async def handle_config(request):
    uuid = request.match_info.get("uuid")
    print(uuid)
    return aiohttp.web.Response(body=json.dumps(conf_file))

app = aiohttp.web.Application()
app.add_routes([aiohttp.web.get('/{uuid}/config',handle_config)])

if __name__ == "__main__":
    aiohttp.web.run_app(app)
