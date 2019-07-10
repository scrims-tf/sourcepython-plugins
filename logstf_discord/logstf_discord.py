from listeners.tick import GameThread
from listeners.tick import Delay
from cvars import ConVar
from messages.hooks import HookUserMessage

from datetime import datetime, timezone
import re
import requests
import json

# Keep track of log files we've already seen
SEEN_LOGS = []

CVAR_DISCORD_TOKEN = None
CVAR_DISCORD_CHANNEL = None

def load():
    global CVAR_DISCORD_TOKEN
    global CVAR_DISCORD_CHANNEL
    CVAR_DISCORD_TOKEN = ConVar("discord_api_key")
    CVAR_DISCORD_CHANNEL = ConVar("discord_channel_id")

def threaded(fn):
    def wrapper(*args, **kwargs):
        thread = GameThread(target=fn, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
    return wrapper

def create_message(channel_id, message_data, files=None):
    global CVAR_DISCORD_TOKEN
    token = CVAR_DISCORD_TOKEN.get_string()
    auth_headers = {
        "authorization": "Bot " + token,
        "Content-Type": 'application/json'
    }
    base_url = "https://discordapp.com/api"

    if isinstance(message_data, dict):
        message_data = json.dumps(message_data)

    return requests.post(
        f"{base_url}/channels/{channel_id}/messages",
        data=message_data,
        files=files,
        headers=auth_headers
    )

@HookUserMessage('SayText2')
def SayText2_hook(recipients, data):
    if "Logs were uploaded to: " in data['message']:
        matches = re.search("logs.tf/([0-9]+)", data['message'])
        logid = str(matches[1])
        global SEEN_LOGS
        if logid in SEEN_LOGS:
            return

        SEEN_LOGS.append(logid)
        Delay(5, handle_logupload, tuple([logid]))

@threaded
def handle_logupload(logid):
    response = requests.get(f"http://logs.tf/json/{logid}")
    log_data = response.json()

    date = datetime.fromtimestamp(log_data['info']['date'], timezone.utc).astimezone()
    date = date.strftime("%B %d, %Y @ %I:%M %p %Z")
    link = f"https://logs.tf/{logid}"
    title = log_data['info']['title']
    map = log_data['info']['map']

    embed = {
        "title": title,
        "description": f"*{date}*\n{map}\n\n**{link}**"
    }
    global CVAR_DISCORD_CHANNEL
    channel_id = CVAR_DISCORD_CHANNEL.get_string()

    create_message(channel_id, {"embed": embed})
