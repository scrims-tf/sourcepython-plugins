# =============================================================================
# >> IMPORTS
# =============================================================================
# Source.Python Imports
from commands.typed import TypedServerCommand
from cvars import ConVar
from cvars import cvar
from engines.server import execute_server_command
import paths

# Core Imports
from os import walk
from os.path import abspath, join, basename
import re

# =============================================================================
# >> COMMANDS
# =============================================================================
@TypedServerCommand("sp_exec")
def on_sp_exec(command_info, cfg:str):
    sp_exec(cfg)

# =============================================================================
# >> FUNCTIONS
# =============================================================================
def sp_exec(cfg_file):
    """
        Takes a config name just like the exec command does
        Will execute each line by setting the cvar or running the command
        When it reaches an exec, it will recursively run that exec command
    """
    cfg = search_for_cfg(cfg_file)
    
    if cfg is False:
        print(f"Config file \"{cfg_file}\" not found")
        return

    with open(cfg) as file:
        print(f"SP_EXEC: Executing {cfg}...")
        for line in file:
            nline = normalize_line(line)

            # Find next file to exec
            if nline.startswith("exec "):
                args = nline.split(" ", 1)
                if len(args) != 2:
                    print(f"Invalid exec command: {nline}")
                    continue
                
                target = re.sub(".cfg$", "", args[1])
                sp_exec(target)
                continue
            elif nline.startswith("mp_tournament_whitelist "):
                args = nline.split(" ", 1)
                if len(args) != 2:
                    print(f"Invalid whitelist command: {nline}")
                    continue
    
                target = re.sub(".txt$", "", args[1])
                file = search_for_cfg(target, extension="txt")

                with open(file, 'rb') as src, open(join(paths.GAME_PATH, "cfg/whitelist.txt"), 'wb') as dst:
                    dst.write(src.read())
                
                ConVar("mp_tournament_whitelist").set_string("cfg/whitelist.txt")

                continue
            # Run command or set cvar
            not_commands = ["sv_pure", "log", "tv_msg"]
            
            var = nline.split(" ", 1)[0]
            base = cvar.find_base(var)
            if base is None:
                continue
            elif base.is_command() and var not in not_commands:
                try:
                    execute_server_command(nline)
                except Exception as e:
                    print(e)
                    continue
            else:
                var, val = nline.split(" ", 1)
                ConVar(var).set_string(val)

def normalize_line(line):
    line = line.replace("\n", "")
    line = re.sub(" ?//.*$", "", line)
    line = re.sub("\t", " ", line)
    line = re.sub("\"", "", line)
    
    return line

def search_for_cfg(filename, extension="cfg"):
    """
        Finds a cfg inside of srcds's default search paths
        Returns the first matching cfg it can find
    """
    search_paths = ["cfg", "custom"]
    
    for search_path in search_paths:
        for root, dirs, files in walk(join(paths.GAME_PATH, search_path)):
            for file in files:
                if file.endswith(f"{basename(filename)}.{extension}"):
                    return abspath(join(root, file))

    return False
