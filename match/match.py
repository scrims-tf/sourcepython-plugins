# =============================================================================
# >> IMPORTS
# =============================================================================
# SP Imports
from cvars import ConVar
from colors import ORANGE, WHITE
from events import Event
from listeners.tick import GameThread
from events.hooks import EventAction, PreEvent
from engines.server import execute_server_command, global_vars, engine_server
from listeners import ListenerManager, ListenerManagerDecorator
from commands.typed import TypedSayCommand, TypedServerCommand, TypedClientCommand
from filters.players import PlayerIter, Player
from memory import get_virtual_function
from memory.hooks import PreHook
from messages import SayText2
from paths import GAME_PATH
from entities.entity import Entity
from weapons.entity import Weapon
from messages import VGUIMenu

# Core Imports
from os.path import join
from shutil import move
from time import time
from enum import Enum
from datetime import datetime, timedelta
from zipfile import ZipFile
import re
import json
import math

# Third Party Libraries
import requests
import boto3

# =============================================================================
# >> MATCH VARIABLES
# =============================================================================
MATCH_IN_PROGRESS = False
MATCH_COUNTDOWN_IN_PROGRESS = False
MATCH_NAME = None
MATCH_MAP_NAME = ""
MATCH_LOG_URL = None

MATCH_RED_TEAM_NAME = ""
MATCH_BLUE_TEAM_NAME = ""

MATCH_START_TIME = None
MATCH_END_TIME = None

# =============================================================================
# >> CVARS
# =============================================================================
CVAR_DISCORD_API_KEY = ""
CVAR_DISCORD_CHANNEL = ""
CVAR_LOGSTF_KEY = ""
CVAR_DEMOSTF_KEY = ""
CVAR_ARCHIVE_BUCKET = ""

CVAR_GAMEMODE = ""
CVAR_RESERVATION_ID = ""

def threaded(fn):
    def wrapper(*args, **kwargs):
        thread = GameThread(target=fn, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
    return wrapper

# =============================================================================
# >> CUSTOM EVENTS
# =============================================================================
class MatchStart(ListenerManagerDecorator):
    # Fires when players start the match
    manager = ListenerManager()

class MatchCountdown(ListenerManagerDecorator):
    # Fires when the match is about to begin - teamplay_round_restart_seconds
    manager = ListenerManager()

class MatchReset(ListenerManagerDecorator):
    # Fires when match was going to start but cancels
    manager = ListenerManager()

class MatchEnd(ListenerManagerDecorator):
    # Fires when match ends
    manager = ListenerManager()

# =============================================================================
# >> EVENT TRIGGERS
# =============================================================================
@Event("teamplay_round_start")
def on_teamplay_round_start(event):
    global MATCH_IN_PROGRESS
    global MATCH_COUNTDOWN_IN_PROGRESS
    global MATCH_START_TIME
    
    if MATCH_IN_PROGRESS is True:
        return

    if ConVar("mp_tournament").get_bool() is False:
        return
    
    if MATCH_COUNTDOWN_IN_PROGRESS is False:
        return
        
    MATCH_COUNTDOWN_IN_PROGRESS = False

    MATCH_IN_PROGRESS = True
    MATCH_START_TIME = datetime.utcnow()
    MatchStart.manager.notify()

@Event("teamplay_round_restart_seconds")
def on_teamplay_round_restart_seconds(event):
    global MATCH_COUNTDOWN_IN_PROGRESS
    MATCH_COUNTDOWN_IN_PROGRESS = True

    MatchCountdown.manager.notify()

@Event("tf_game_over")       # Only fires when winlimit reached
@Event("teamplay_game_over") # Only fires when timelimit reached
def on_tf_game_over(event):
    global MATCH_IN_PROGRESS
    global MATCH_END_TIME
    global MATCH_COUNTDOWN_IN_PROGRESS
    
    if MATCH_IN_PROGRESS is False:
        return

    if ConVar("mp_tournament").get_bool() is False:
        return
    
    if MATCH_COUNTDOWN_IN_PROGRESS is True:
        MATCH_COUNTDOWN_IN_PROGRESS = False
        return

    MATCH_IN_PROGRESS = False
    MATCH_END_TIME = datetime.utcnow()
    MatchEnd.manager.notify()

# TODO Add endmatch command

# =============================================================================
# >> ON LOAD
# =============================================================================
def load():
    global CVAR_DISCORD_API_KEY
    global CVAR_DISCORD_CHANNEL
    global CVAR_LOGSTF_KEY
    global CVAR_DEMOSTF_KEY
    global CVAR_ARCHIVE_BUCKET
    global CVAR_GAMEMODE
    global CVAR_RESERVATION_ID
    
    CVAR_DISCORD_API_KEY = ConVar("discord_api_key")
    CVAR_DISCORD_CHANNEL = ConVar("discord_channel_id")
    CVAR_LOGSTF_KEY = ConVar("logstf_api_key")
    CVAR_DEMOSTF_KEY = ConVar("demostf_api_key")
    CVAR_ARCHIVE_BUCKET = ConVar("archive_s3_bucket")

    CVAR_GAMEMODE = ConVar("sp_gamemode")
    CVAR_RESERVATION_ID = ConVar("sp_hostname")

    execute_server_command("tv_stoprecord")

def unload():
    execute_server_command("tv_stoprecord")

# =============================================================================
# >> Commands
# =============================================================================
@TypedSayCommand("!logs")
@TypedClientCommand("sp_logs")
def on_showlogs(command_info):
    global MATCH_LOG_URL

    # https://github.com/Source-Python-Dev-Team/Source.Python/issues/315
    # Seems to crash if people ask for logs too quickly?
    if MATCH_LOG_URL is None or not isinstance(MATCH_LOG_URL, str):
        SayText2("No log exists yet!").send(command_info.index)
        return
    
    subkeys = {'title': "Logs", 'type': '2', 'msg': MATCH_LOG_URL}
    VGUIMenu("info", subkeys=subkeys, show=True).send(command_info.index)

# =============================================================================
# >> ON LOAD
# =============================================================================
@MatchStart
def on_match_start():
    global MATCH_NAME
    global MATCH_IN_PROGRESS
    global MATCH_NAME
    global MATCH_MAP_NAME
    global MATCH_RED_TEAM_NAME
    global MATCH_BLUE_TEAM_NAME
    
    # Stop any existing recording
    execute_server_command("tv_stoprecord")

    # Setup the match logs and demo
    MATCH_RED_TEAM_NAME = ConVar("mp_tournament_redteamname").get_string()
    MATCH_BLUE_TEAM_NAME = ConVar("mp_tournament_blueteamname").get_string()
    gametype, MATCH_MAP_NAME, *version = global_vars.map_name.split("_")

    MATCH_NAME = f"{MATCH_RED_TEAM_NAME}-v-{MATCH_BLUE_TEAM_NAME}-{int(time())}-{MATCH_MAP_NAME}".lower()

    # Start demo recording
    execute_server_command("tv_record", MATCH_NAME)
    SayText2(f"Recording STV: {ORANGE}{MATCH_NAME}.dem").send()

    # Create log file
    open(join(GAME_PATH, f"matches/{MATCH_NAME}.log"), "w").close()
    SayText2(f"Match log: {ORANGE}{MATCH_NAME}.log").send()

    teams = ["un", "spec", "red", "blue"]
    classes = ["scout", "sniper", "soldier", "demoman", "medic", "heavy", "pyro", "spy", "engineer"]

    # TODO: why are these getting eaten?
    for player in PlayerIter("human"):
        log_print(
            f"\"{player.name}<{player.userid}><{player.steamid}><{teams[player.team].capitalize()}>\""
            f" changed role to \"{classes[player.player_class - 1].lower()}\""
        )

    log_print("World triggered \"Round_Start\"")

    for player in PlayerIter("human"):  
        log_print(
            f"\"{player.name}<{player.userid}><{player.steamid}><{teams[player.team].capitalize()}>\""
            f" spawned as \"{ classes[player.player_class - 1].lower()}\""
        )

@MatchEnd
def on_match_end():
    # Stop recording
    execute_server_command("tv_stoprecord")
    SayText2(f"Game over! Uploading logs and demos...").send()

    move(join(GAME_PATH, f"{MATCH_NAME}.dem"), join(GAME_PATH, "matches"))
    upload_all()

# =============================================================================
# >> Upload Functions
# =============================================================================
@threaded
def upload_all():
    global MATCH_NAME
    global CVAR_ARCHIVE_BUCKET

    # Upload logs to logs.tf and demos.tf
    demostf_url = upload_to_demostf()
    logstf_url = upload_to_logstf()
    s3_url = f"http://{CVAR_ARCHIVE_BUCKET.get_string()}/{MATCH_NAME}/{MATCH_NAME}.zip"
    upload_to_discord(logstf_url, demostf_url, s3_url)

    # S3 upload / compress could take a while so we don't wanna block notifiyng users if this is just an long term archive
    upload_to_s3()

def upload_to_s3():
    global MATCH_NAME
    global CVAR_ARCHIVE_BUCKET
    
    demo_path = join(GAME_PATH, f"matches/{MATCH_NAME}.dem")
    log_path = join(GAME_PATH, f"matches/{MATCH_NAME}.log")
    zip_path = join(GAME_PATH, f"matches/{MATCH_NAME}.zip")
    
    s3 = boto3.client("s3")
    with open(log_path, "rb") as file:
        response = s3.put_object(Bucket=CVAR_ARCHIVE_BUCKET.get_string(), Body=file, Key=f"{MATCH_NAME}/{MATCH_NAME}.log")
        raise_for_status(response)

    with open(demo_path, "rb") as file:
        response = s3.put_object(Bucket=CVAR_ARCHIVE_BUCKET.get_string(), Body=file, Key=f"{MATCH_NAME}/{MATCH_NAME}.dem")
        raise_for_status(response)
    
    zip = ZipFile(zip_path, "w")
    zip.write(demo_path)
    zip.write(log_path)
    
    with open(zip_path, "rb") as file:
        response = s3.put_object(Bucket=CVAR_ARCHIVE_BUCKET.get_string(), Body=file, Key=f"{MATCH_NAME}/{MATCH_NAME}.zip")
        raise_for_status(response)
    
    return f"http://{CVAR_ARCHIVE_BUCKET.get_string()}/{MATCH_NAME}/{MATCH_NAME}.zip"

def upload_to_logstf():
    global MATCH_NAME
    global MATCH_MAP_NAME
    global MATCH_LOG_URL
    global MATCH_RED_TEAM_NAME
    global MATCH_BLUE_TEAM_NAME
    global CVAR_LOGSTF_KEY
    
    logs_tf_data = {
        "title": f"{MATCH_RED_TEAM_NAME} vs {MATCH_BLUE_TEAM_NAME}",
        "map": MATCH_MAP_NAME,
        "key": CVAR_LOGSTF_KEY.get_string(),
        "uploader": "SourcePython Match Plugin by Zeus"
    }
    log_path = join(GAME_PATH, f"matches/{MATCH_NAME}.log")

    with open(log_path, "rb") as file:
        response = requests.post("http://logs.tf/upload", data=logs_tf_data, files={"logfile": file})
        response.raise_for_status()

    log_id = response.json()['log_id']
    log_url = f"http://logs.tf/{log_id}"
    MATCH_LOG_URL = log_url
    SayText2(f"Logs uploaded to: {ORANGE}{log_url}{WHITE}.\nType {ORANGE}!logs {WHITE}to see stats.").send()

    return log_url

def upload_to_demostf():
    global MATCH_NAME
    global MATCH_RED_TEAM_NAME
    global MATCH_BLUE_TEAM_NAME
    
    demos_tf_data = {
        "title": f"{MATCH_RED_TEAM_NAME} vs {MATCH_BLUE_TEAM_NAME}",
        "red": MATCH_RED_TEAM_NAME,
        "blu": MATCH_BLUE_TEAM_NAME,
        "key": CVAR_DEMOSTF_KEY.get_string()
    }
    
    demo_path = join(GAME_PATH, f"matches/{MATCH_NAME}.dem")
    with open(demo_path, "rb") as file:
        response = requests.post("https://api.demos.tf/upload", data=demos_tf_data, files={"demo": file})
        response.raise_for_status()
    
    demo_id = re.search("[0-9]+$", response.text).group()
    demo_url = f"https://demos.tf/{demo_id}"
    SayText2(f"STV Demo uploaded to: {ORANGE}{demo_url}").send()

    return demo_url

def upload_to_discord(logstf_url, demostf_url, archive_url):
    global MATCH_START_TIME
    global MATCH_END_TIME
    global MATCH_MAP_NAME
    global MATCH_RED_TEAM_NAME
    global MATCH_BLUE_TEAM_NAME
    
    global CVAR_DISCORD_CHANNEL
    global CVAR_GAMEMODE
    global CVAR_RESERVATION_ID

    elapsed_seconds = (MATCH_END_TIME - MATCH_START_TIME).seconds
    elapsed_time = f"{math.floor(elapsed_seconds/60):02}:{elapsed_seconds % 60:02}"
    reservation_id = CVAR_RESERVATION_ID.get_string()
    
    embed = {
        "title": f"{MATCH_RED_TEAM_NAME} vs {MATCH_BLUE_TEAM_NAME}",
        "description": f"*{CVAR_GAMEMODE.get_string()}*\n\n[**Logs**]({logstf_url}) • [**Demo**]({demostf_url}) • [**Archive**]({archive_url})",
        "fields": [
            {
                "name": "Duration",
                "value": f"{elapsed_time}",
                "inline": True
            },
            {
                "name": "Map",
                "value": f"{MATCH_MAP_NAME.capitalize()}",
                "inline": True
            },
            {
                "name": "Reservation ID",
                "value": f"`{reservation_id}`",
                "inline": True
            }
        ],
        "timestamp": MATCH_START_TIME.isoformat()
    }
    channel_id = CVAR_DISCORD_CHANNEL.get_string()
    create_message(channel_id, {"embed": embed})

@PreHook(get_virtual_function(engine_server, 'LogPrint'))
def on_log_print(args):
    global MATCH_IN_PROGRESS
    global MATCH_NAME

    if MATCH_IN_PROGRESS is True and MATCH_NAME is not None:
        message = args[1]
        with open(join(GAME_PATH, f"matches/{MATCH_NAME}.log"), "a") as file:
            datestamp = datetime.now().strftime("%m/%d/%Y - %H:%M:%S")
            file.write(f"L {datestamp}: {message}")

    return EventAction.BLOCK

# =============================================================================
# >> Util Functions
# =============================================================================
def log_print(message):
    if "\n" not in message:
        message += "\n"

    engine_server.log_print(message)

def create_message(channel_id, message_data, files=None):
    global CVAR_DISCORD_API_KEY

    token = CVAR_DISCORD_API_KEY.get_string()
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

def raise_for_status(boto_response):
    status_code = boto_response['ResponseMetadata']['HTTPStatusCode']
    if status_code != 200:
        raise Exception("Boto returned HTTP {}".format(status_code))
