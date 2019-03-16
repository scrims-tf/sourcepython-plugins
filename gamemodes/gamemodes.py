# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Imports
from colors import ORANGE, WHITE
from commands.typed import TypedSayCommand, TypedServerCommand
from cvars import ConVar
from engines.server import execute_server_command
from filters.players import PlayerIter
from listeners.tick import Delay
from listeners import OnLevelInit
from menus.radio import PagedRadioOption, PagedRadioMenu
from messages import SayText2
import paths

# Core Imports
from enum import Enum, auto
from collections import defaultdict
import random
import json
import os.path

# =============================================================================
# >> GLOBAL VARIABLES
# =============================================================================
class MenuChoice(Enum):
    SET_GAME_MODE = auto()
    CHANGE_MAP = auto()
    CALL_MAP_VOTE = auto()
    END_ROUND = auto()
    
CURRENT_MODE = None
CURRENT_MAP = None
CURRENT_CONFIG = None

CURRENT_VOTE = defaultdict(int)
CURRENT_VOTE_IN_PROGRESS = False
CURRENT_VOTE_COUNT = 0

GAMEMODES = {}

# ConVars
CVAR_HOSTNAME = None
CVAR_LOCATION = None

# =============================================================================
# >> ON LOAD
# =============================================================================
def load():
    global CURRENT_MODE
    global GAMEMODES
    global CVAR_HOSTNAME
    global CVAR_LOCATION

    CVAR_HOSTNAME = ConVar("sp_hostname", "TF2 Server", description="Cannonical name of the server")
    CVAR_LOCATION = ConVar("sp_location", "Pyroland", description="City the server is located in")

    GAMEMODES = load_config("gamemodes.json")

@OnLevelInit
def on_level_init(map_name):
    global CURRENT_MAP
    global CURRENT_MODE
    global CURRENT_CONFIG
    
    CURRENT_MAP = map_name

    if CURRENT_CONFIG is not None:
        def do():
            execute_server_command("exec", CURRENT_CONFIG)
            set_hostname()
        Delay(1, do)

    if CURRENT_MODE is None:
        CURRENT_MODE = GAMEMODES['DEFAULT']
        rand = random.choice(GAMEMODES[CURRENT_MODE]["maps"])
        change_level(rand['map'], rand['config'])
    
    if GAMEMODES[CURRENT_MODE]['shuffle']:
        rand = random.choice(GAMEMODES[CURRENT_MODE]["maps"])
        ConVar("sm_nextmap").set_string(rand['map'])
    else:
        ConVar("sm_nextmap").set_string(CURRENT_MAP)
    
# =============================================================================
# >> COMMANDS
# =============================================================================
@TypedSayCommand("!menu", permission="gamemode.menu")
def on_say_main_menu(command_info):
    show_main_menu(command_info.index)
    
@TypedSayCommand("!rtv", permission="gamemode.vote")
@TypedSayCommand("!vote", permission="gamemode.vote")
def on_vote(command_info):
    global CURRENT_VOTE_IN_PROGRESS
    
    if CURRENT_VOTE_IN_PROGRESS is True:
        command_info.reply("A vote is already in progress!")
        return
    
    for player in PlayerIter('human'):
        player.play_sound("ui/vote_started.wav")
        show_vote_menu(player.index)
        
    CURRENT_VOTE_IN_PROGRESS = True
    Delay(10, on_vote_tally)

# =============================================================================
# >> MENU HANDLERS
# =============================================================================
def on_fail(command_info, args):
    command_info.reply(f"{ORANGE}System{WHITE}: You do not have access to this command")

def on_select_submenu(options, index, choice):
    if choice.value == MenuChoice.SET_GAME_MODE:
        show_set_game_mode_menu(index)
    elif choice.value == MenuChoice.CHANGE_MAP:
        show_change_map_menu(index)
    elif choice.value == MenuChoice.END_ROUND:
        execute_server_command("exec", "endround")
    elif choice.value == MenuChoice.CALL_MAP_VOTE:
        global CURRENT_VOTE_IN_PROGRESS
        
        if CURRENT_VOTE_IN_PROGRESS is True:
            return
        
        for player in PlayerIter('human'):
            player.play_sound("ui/vote_started.wav")
            show_vote_menu(player.index)
            
        CURRENT_VOTE_IN_PROGRESS = True
        Delay(10, on_vote_tally)
    
def on_select_mode(options, index, choice):
    global CURRENT_MODE
    CURRENT_MODE = choice.value
    
    SayText2(f"Game mode has been changed to: {ORANGE}{choice.value}").send()
    show_change_map_menu(index)

def on_select_map(options, index, choice):
    if isinstance(choice.value, str) and choice.value == "random":
        rand = random.choice(GAMEMODES[CURRENT_MODE]["maps"])
        map = rand['map']
        config = rand['config']
        change_level(map, config)
    elif isinstance(choice.value, dict):
        map = choice.value['map']
        config = choice.value['config']
        change_level(map, config)

def on_vote_submit(options, index, choice):
    global CURRENT_VOTE
    global CURRENT_VOTE_COUNT

    for player in PlayerIter('human'):
        player.play_sound("ui/vote_yes.wav")

    if isinstance(choice.value, str) and choice.value == "random":
        CURRENT_VOTE[choice.value] += 1
    elif isinstance(choice.value, dict):
        CURRENT_VOTE[choice.value['name']] += 1
    
    CURRENT_VOTE_COUNT += 1

def on_vote_tally():
    global CURRENT_VOTE
    global CURRENT_VOTE_COUNT
    global CURRENT_VOTE_IN_PROGRESS
    
    sorted_votes = sorted(CURRENT_VOTE.items(), key=lambda i: i[1], reverse=True)
    choice = None
    
    if len(sorted_votes) == 0:
        SayText2("No one voted! Picking a map at random...").send()
        choice = "random"
    else:
        winner = sorted_votes[0]
        choice = winner[0]
        percent = int((winner[1] / CURRENT_VOTE_COUNT) * 100)

        for player in PlayerIter('human'):
            player.play_sound("ui/vote_success.wav")
            SayText2(f"Vote winner: {ORANGE}{winner[0]} {WHITE}with {ORANGE}{percent}% {WHITE}votes").send(player.index)
    
    CURRENT_VOTE_IN_PROGRESS = False
    CURRENT_VOTE_COUNT = 0
    CURRENT_VOTE = defaultdict(int)

    global CURRENT_MODE
    global CURRENT_CONFIG
    
    if choice == "random":
        rand = random.choice(GAMEMODES[CURRENT_MODE]["maps"])
        change_level(rand['map'], rand['config'])
    else:
        for item in GAMEMODES[CURRENT_MODE]["maps"]:
            if item['name'] == choice:
                change_level(item['map'], item['config'])
    
# =============================================================================
# >> MENU DISPLAY FUNCTIONS
# =============================================================================
def show_main_menu(index):
    menu = PagedRadioMenu(
        data=[
            PagedRadioOption("Set game mode", value=MenuChoice.SET_GAME_MODE),
            PagedRadioOption("Change map", value=MenuChoice.CHANGE_MAP),
            PagedRadioOption("Call Map Vote", value=MenuChoice.CALL_MAP_VOTE),
            PagedRadioOption("End Round", value=MenuChoice.END_ROUND)
        ],
        title="Main Menu",
        select_callback=on_select_submenu
    )
    menu.send(index)
    
def show_set_game_mode_menu(index):
    global GAMEMODES
    global CURRENT_MODE
    
    gamemodes = list(GAMEMODES.keys())
    gamemodes.remove("DEFAULT")
    
    menu = PagedRadioMenu(
        data=[PagedRadioOption(mode, value=mode) for mode in gamemodes],
        title="Game Modes",
        select_callback=on_select_mode
    )
    menu.send(index)

def show_change_map_menu(index):
    global GAMEMODES
    global CURRENT_MODE

    options = [PagedRadioOption("Random", value="random")]
    for item in sorted(GAMEMODES[CURRENT_MODE]["maps"], key=lambda i: i['name']):
        options.append(PagedRadioOption(item["name"], value=item))

    menu = PagedRadioMenu(
        data=options,
        title="Map Selection",
        select_callback=on_select_map
    )
    menu.send(index)

def show_vote_menu(index):
    global CURRENT_VOTE
    global GAMEMODES
    global CURRENT_MODE
    global ALL_MENUS

    CURRENT_VOTE = defaultdict(int)

    options = [PagedRadioOption("Random", value="random")]
    for item in sorted(GAMEMODES[CURRENT_MODE]["maps"], key=lambda i: i['name']):
        options.append(PagedRadioOption(item["name"], value=item))

    menu = PagedRadioMenu(
        data=options,
        title="Map Vote",
        select_callback=on_vote_submit
    )
    menu.send(index)

# =============================================================================
# >> UTILITY FUNCTIONS
# =============================================================================
def load_config(filepath):
    with open(os.path.join(paths.GAME_PATH, filepath)) as file:
        return json.loads(file.read())

def change_level(map, config):
    global CURRENT_MAP
    global CURRENT_CONFIG
    
    CURRENT_MAP = map
    CURRENT_CONFIG = config

    SayText2(f"Map will be changed to: {ORANGE}{CURRENT_MAP} {WHITE}in {ORANGE}5 {WHITE}seconds...").send()

    for player in PlayerIter('human'):
        player.play_sound("items/cart_explode_trigger.wav")
    
    def do():
        set_hostname()
        execute_server_command("exec", CURRENT_CONFIG)
        execute_server_command("changelevel", CURRENT_MAP)
    Delay(5, do)
    
def set_hostname():
    global CVAR_HOSTNAME
    global CVAR_LOCATION
    global CURRENT_MODE

    hostname = CVAR_HOSTNAME.get_string()
    location = CVAR_LOCATION.get_string()

    ConVar("hostname").set_string(f"{hostname} | {CURRENT_MODE} | {location}")
