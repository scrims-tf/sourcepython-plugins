# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Imports
from commands.typed import TypedSayCommand, TypedClientCommand
from engines.server import engine_server
from entities.helpers import index_from_edict
from filters.players import PlayerIter, Player
from colors import ORANGE, WHITE

# Core Imports
import random

# =============================================================================
# >> FILTERS
# =============================================================================
def player_filter(value):
    value = str(value).lower()
    
    if value in ["all", "bot", "human", "bot", "alive", "dead"]:
        yield from PlayerIter(value)
    elif value == "blu":
        yield from PlayerIter("ct")
    elif value == "red":
        yield from PlayerIter("t")
    elif value == "spec":
        yield from PlayerIter("spec")
        yield from PlayerIter("un")
    else:
        for player in PlayerIter():
            if player.name.lower().startswith(value):
                yield player
                break
        else:
            raise Exception

# =============================================================================
# >> COMMANDS
# =============================================================================
@TypedSayCommand("!spec", permission="admin.move_players")
@TypedClientCommand("sp_spec", permission="admin.move_players")
def on_move_to_spec(command_info, players:player_filter):
    for player in players:
        player.set_team(1)

@TypedSayCommand("!blu", permission="admin.move_players")
@TypedClientCommand("sp_blu", permission="admin.move_players")
def on_move_to_blu(command_info, players:player_filter):
    for player in players:
        player.set_team(3)
        
@TypedSayCommand("!red", permission="admin.move_players")
@TypedClientCommand("sp_red", permission="admin.move_players")
def on_move_to_red(command_info, players:player_filter):
    for player in players:
        player.set_team(2)

@TypedSayCommand("!ban", permission="admin.kick")
@TypedClientCommand("sp_ban", permission="admin.kick")
def on_ban(command_info, players:player_filter):
    kicker = Player(command_info.index)
    for player in players:
        player.ban()
        
@TypedSayCommand("!kick", permission="admin.kick")
@TypedClientCommand("sp_kick", permission="admin.kick")
def on_kick(command_info, players:player_filter):
    kicker = Player(command_info.index)
    for player in players:
        player.kick(f"You were kicked by {kicker.name}")
    
@TypedSayCommand("!mute", permission="admin.mute")
@TypedClientCommand("sp_mute", permission="admin.mute")
def on_mute(command_info, players:player_filter):
    for player in players:
        player.mute()

@TypedSayCommand("!unmute", permission="admin.mute")
@TypedClientCommand("sp_unmute", permission="admin.mute")
def on_unmute(command_info, players:player_filter):
    for player in players:
        player.unmute()

@TypedSayCommand("!slay", permission="admin.slay")
@TypedSayCommand("!kys", permission="admin.slay")
@TypedClientCommand("sp_slay", permission="admin.slay")
def on_kys(command_info, players:player_filter):
    for player in players:
        if player.team in [2,3]:
            player.play_sound(f"player/shove{random.randint(1,10)}.wav")
            player.slay()

@TypedSayCommand("!name", permission="admin.rename")
@TypedClientCommand("sp_name", permission="admin.rename")
def on_name(command_info, players:player_filter, new_name:str):
    for player in players:
        player.set_name(new_name)

@TypedSayCommand("!noclip", permission="admin.noclip")
@TypedClientCommand("sp_noclip", permission="admin.noclip")
def on_noclip(command_info, players:player_filter):
    for player in players:
        player.set_noclip(not player.noclip)

@TypedSayCommand("!steamid", permission="admin.info")
@TypedClientCommand("sp_steamid", permission="admin.info")
def on_steamid(command_info, players:player_filter):
    for player in players:
        command_info.reply(f"{WHITE}Name: {ORANGE}{player.name}{WHITE}, STEAM_ID: {ORANGE}{player.steamid}")

@TypedSayCommand("!rup", permission="admin.rup")
@TypedClientCommand("rup", permission="admin.rup")
def on_rup(command_info):
    teams = {"RED":2, "BLU": 3}
    for team_name, team_id in teams.items():
        fake_client = engine_server.create_fake_client(f'RUP BOT {team_name}')
        fake_player = Player(index_from_edict(fake_client))
        fake_player.team = team_id
        fake_player.client_command("tournament_readystate 1", True)
        fake_player.kick()        
        
