# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Imports
from events import Event
from engines.server import global_vars
from listeners import *
from listeners.tick import Repeat
from listeners.tick import GameThread
from messages.hooks import HookUserMessage
from players.entity import Player
from paths import LOG_PATH
from filters.players import PlayerIter

# Core Imports
import time
import os.path
import json

# =============================================================================
# >> IMPORTS
# =============================================================================
CURRENT_MAP_START = 0
CONNECTED_PLAYERS = {}
SERVER_IDLE_START = -1
SERVER_IDLE_DURATION = 0
LOG_PLAYERS_LOOP = None

# =============================================================================
# >> ON LOAD
# =============================================================================
def load():
    global LOG_PLAYERS_LOOP
    LOG_PLAYERS_LOOP = Repeat(log_players)
    LOG_PLAYERS_LOOP.start(5, execute_on_start=True)

# =============================================================================
# >> UTILITY FUNCTIONS
# =============================================================================
def threaded(fn):
    def wrapper(*args, **kwargs):
        thread = GameThread(target=fn, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
    return wrapper
    
@threaded
def log_value(logfile, value):
    with open(os.path.join(LOG_PATH, logfile), "w") as file:
        file.truncate()
        file.write(str(value))

@threaded
def log_json(event_name, event_data, logfile="event.log"):
    timestamp = int(time.time())

    message = {
        "time": timestamp,
        "event_name": event_name,
        "event": event_data
    }
    with open(os.path.join(LOG_PATH, logfile), "a") as file:
        file.write(json.dumps(message))
        file.write("\n")

# =============================================================================
# >> EVENT HANDLERS
# =============================================================================
@OnLevelInit
def log_level_init(map_name):
    global CURRENT_MAP_START
    CURRENT_MAP_START = int(time.time())
    log_json("level_init", {"level_name": global_vars.map_name})
    log_value("currentmap", global_vars.map_name)

@OnLevelEnd
def log_level_end():
    global CURRENT_MAP_START
    if CURRENT_MAP_START == 0:
        return

    current_time = int(time.time())
    elapsed = int(current_time) - int(CURRENT_MAP_START)
    message = {"level_duration": elapsed, "level_name": global_vars.map_name}
    log_json("level_end", message)

@Event("player_connect")
def log_player_connect(event):
    args = event.variables.as_dict()
    log_players()
    message = {
        "player": {
            "bot": bool(args['bot']),
            "ip_address": args['address'],
            "name": args['name'],
            "steamid": args['networkid']
        }
    }
    log_json("player_connect", message)

    global CONNECTED_PLAYERS
    CONNECTED_PLAYERS[args['networkid']] = {
        "connection_time": int(time.time())
    }

@Event("player_disconnect")
def log_player_disconnect(event):
    args = event.variables.as_dict()
    player = Player.from_userid(args['userid'])
    log_players()
    message = {
        "player": {
            "name": player.name,
            "steamid": player.steamid,
            "reason": args['reason']
        }
    }

    global CONNECTED_PLAYERS
    try:
        connection_time = CONNECTED_PLAYERS.pop(player.steamid)['connection_time']
        total_playtime = int(time.time()) - connection_time

        message.update({"playtime": total_playtime})
    except KeyError:
        pass
    finally:
        log_json("player_disconnect", message)

@Event("server_addban")
def log_player_ban(event):
    args = event.variables.as_dict()

    message = {
        "type": "kick" if bool(args['kicked']) else "ban",
        "ban_duration": args['duration'],
        "banning_player": args['by'],
        "banned_player": {
            "name": args['name'],
            "steamid": args['networkid'],
            "ip_address": args['ip']
        }
    }
    log_json("player_banned", message)

@Event("player_changename")
def log_player_changename(event):
    args = event.variables.as_dict()
    player = Player.from_userid(args['userid'])

    message = {
        "old_name": args['oldname'],
        "new_name": args['newname'],
        "player": {
            "steamid": player.steamid
        }
    }
    log_json("player_namechange", message)

def log_player_badpassword():
    raise NotImplementedError

def log_failed_rcon_password():
    raise NotImplementedError

@HookUserMessage('SayText2')
def log_chat(recipients, data):
    if data.index == 0:
        return True

    if data.param2 == "":
        return True

    player = Player(data.index)
    teams = ["unassigned", "spectate", "red", "blue"]

    team_only = bool(data.message in ["TF_Chat_Team_Dead", "TF_Chat_Team"])

    message = {
        "team_only": team_only,
        "message": data.param2,
        "player": {
            "steamid": player.steamid,
            "name": player.name,
            "team": player.team,
            "team_name": teams[player.team]
        }
    }
    log_json("player_chat", message, logfile="chat.log")
    return True

@Event("player_changeclass")
def log_class_change(event):
    args = event.variables.as_dict()
    player = Player.from_userid(args['userid'])
    teams = ["unassigned", "spectate", "red", "blue"]
    classes = ["scout","sniper","soldier","demoman","medic","heavy","pyro","spy","engineer"]

    message = {
        "class": args['class'],
        "class_name": classes[args['class']-1],
        "player": {
            "steamid": player.steamid,
            "name": player.name,
            "team": player.team,
            "team_name": teams[player.team-1]
        }
    }
    log_json("player_change_class", message)

@Event("player_team")
def log_team_change(event):
    args = event.variables.as_dict()
    player = Player.from_userid(args['userid'])
    teams = ["unassigned", "spectate", "red", "blue"]
    log_players()
    if bool(args['disconnect']):
        return
    else:
        message = {
            "autoassigned": bool(args['autoteam']),
            "oldteam": args['oldteam'],
            "oldteam_name": teams[args['oldteam']-1],
            "player": {
                "steamid": player.steamid,
                "name": player.name,
                "team": player.team,
                "team_name": teams[player.team-1]
            }
        }
        log_json("player_change_team", message)

@threaded
def log_players():
    players = bots = spectators = 0

    for player in PlayerIter():
        if player.is_hltv():
            continue

        if player.is_bot():
            bots += 1
            continue
        elif player.team == 1 or player.team == 0 and not player.is_bot():
            spectators += 1
            continue
        elif not player.is_bot():
            players += 1

    global SERVER_IDLE_START
    global SERVER_IDLE_DURATION
    if players >= 1:
        SERVER_IDLE_START = -1
        SERVER_IDLE_DURATION = 0
    elif players == 0 and spectators < 4 and SERVER_IDLE_START == -1:
        SERVER_IDLE_START = time.time()
        SERVER_IDLE_DURATION = 0
    elif players == 0 and spectators < 4 and SERVER_IDLE_START >= 0:
        SERVER_IDLE_DURATION = time.time() - SERVER_IDLE_START

    log_value("idle", SERVER_IDLE_DURATION)
    log_value("players", players)
    log_value("bots", bots)
    log_value("spectators", spectators)
