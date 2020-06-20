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
            nline = line.replace("\n", "")

            # Find next file to exec
            if nline.startswith("exec "):
                args = nline.split(" ", 1)
                if len(args) != 2:
                    print(f"Invalid exec command: {nline}")
                    continue
                    
                sp_exec(args[1])
                continue
            
            # Run command or set cvar
            base = cvar.find_base(nline)
            if base is None:
                continue
            elif base.is_command():
                execute_server_command(nline)
            else:
                var, val = nline.split(" ", 1)
                ConVar(var).set_string(val)

def search_for_cfg(filename):
    """
        Finds a cfg inside of srcds's default search paths
        Returns the first matching cfg it can find
    """
    search_paths = ["cfg", "custom"]
    
    for search_path in search_paths:
        for root, dirs, files in walk(join(paths.GAME_PATH, search_path)):
            for file in files:
                if file.endswith(f"{basename(filename)}.cfg"):
                    return abspath(join(root, file))

    return False
