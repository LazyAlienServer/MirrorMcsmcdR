DEFAULT_CONFIG = {
    "!!mirror": {
        "mcsm": {
            "enable": False,
            "url": "http://127.0.0.1:23333/",
            "uuid": None,
            "remote_uuid": None,
            "apikey": None
        },
        "terminal": {
            "enable": False,
            "launch_path": "./Mirror",
            "launch_command": "python -m mcdreforged",
            "port": None,
            "terminal_name": "Mirror",
            "regex_strict": False,
            "system": None
        },
        "rcon": {
            "enable": False,
            "address": None,
            "port": None,
            "password": None
        },
        "sync": {
            "world": [
                "world"
            ],
            "source": "./server",
            "target": [
                "./Mirror/server"
            ],
            "ignore_inexistent_target_path": False,
            "concurrency": 4,
            "ignore_files": [
                "session.lock"
            ]
        },
        "command": {
            "permission": {
                "status": 0,
                "start": 0,
                "stop": 2,
                "kill": 3,
                "sync": 2,
                "confirm": 0,
                "abort": 0
            },
            "action": {
                "status": {
                    "require_confirm": False
                },
                "start": {
                    "require_confirm": False
                },
                "stop": {
                    "require_confirm": True
                },
                "kill": {
                    "require_confirm": True
                },
                "sync": {
                    "ensure_server_closed": True,
                    "auto_server_restart": False,
                    "check_status_interval": 5,
                    "max_attempt_times": 3,
                    "save_world": {
                        "turn_off_auto_save": True,
                        "commands": {
                            "save_all_worlds": "save-all flush",
                            "auto_save_off": "save-off",
                            "auto_save_on": "save-on"
                        },
                        "saved_world_regex": "^Saved the game$",
                        "save_world_max_wait_sec": 60
                    },
                    "require_confirm": True
                },
                "confirm": {
                    "timeout": 30,
                    "cancel_anymsg": True
                },
                "abort": {
                    "operator": "everyone"
                }
            }
        },
        "display": {
            "server_name": "Mirror"
        }
    }
}

PLUGIN_ID = "mirror_mcsmcdr"
TITLE = "MirrorMcsmcdR"
REPLY_TITLE = "§e[MirrorMcsmcdR]§f"
VERSION = "1.4.0"