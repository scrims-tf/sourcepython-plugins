# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Imports
from commands.typed import TypedServerCommand
from commands.client import ClientCommandFilter
from cvars import ConVar
from events.hooks import PreEvent, EventAction
from filters.players import PlayerIter
from listeners.tick import GameThread
from players.entity import Player

# Core Imports
import time

# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
FORCED_NAMES = {}
FORCED_TEAMS = {}

# ConVars
CVAR_FORCETEAMS = None
CVAR_FORCENAMES = None

# =============================================================================
# >> ON LOAD
# =============================================================================
def load():
    global CVAR_FORCETEAMS
    global CVAR_FORCENAMES

    CVAR_FORCETEAMS = ConVar("sp_forceteams", "0", description="Enforce manual team assignments")
    CVAR_FORCENAMES = ConVar("sp_forcenames", "0", description="Enforce manual name assignments")

    force_names()

def threaded(fn):
    def wrapper(*args, **kwargs):
        thread = GameThread(target=fn, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
    return wrapper

# =============================================================================
# >> FORCE TEAMS
# =============================================================================
@ClientCommandFilter
def prevent_team_change(command, index):
    global FORCED_TEAMS
    global CVAR_FORCETEAMS
    
    enforcing = CVAR_FORCETEAMS.get_bool()
    if enforcing is not True:
        return True
    
    player = Player(index)
    steamid = player.raw_steamid.to_uint64()

    if command[0] == 'jointeam':
        team_choice = command[1]
        
        if team_choice in ["blue", "red"]:
            forced_team = FORCED_TEAMS.get(steamid, None)
            if forced_team is None:
                return False
            
            team_choice = 2 if team_choice == "red" else 3
                    
            if forced_team == team_choice:
                return True
            else:
                player.play_sound("vo/engineer_no01.mp3")
                return False

@TypedServerCommand("forceteam")
def on_force_team(command_info, steamid: int, team: int):
    global FORCED_TEAMS

    for player in PlayerIter("human"):
        steamid = player.raw_steamid.to_uint64()
        player.set_team(team)
        FORCED_TEAMS[steamid] = team

@TypedServerCommand("forceteam_clear")
def on_force_team_clear(command_info):
    global FORCED_TEAMS
    FORCED_TEAMS = {}
        
# =============================================================================
# >> FORCE NAMES
# =============================================================================
@PreEvent('player_changename')
def on_changename(event):
    global FORCED_NAMES
    
    args = event.variables.as_dict()
    print(args)
    
    player = Player.from_userid(args['userid'])
    steamid = player.raw_steamid.to_uint64()
    forced_name = FORCED_NAMES[steamid]

    if forced_name != args['newname']:
        player.set_name(forced_name)

    return EventAction.STOP_BROADCAST


@TypedServerCommand("forcename")
def on_force_name(command_info, steamid: int, name: str):
    global FORCED_NAMES
    FORCED_NAMES[steamid] = name

@threaded
def force_names():
    global CVAR_FORCENAMES
    
    while CVAR_FORCENAMES.get_bool():
        for player in PlayerIter("human"):
            steamid = player.raw_steamid.to_uint64()
            if steamid in FORCED_NAMES and player.get_name() != FORCED_NAMES[steamid]:
                player.set_name(FORCED_NAMES[steamid])
        
        time.sleep(10)
