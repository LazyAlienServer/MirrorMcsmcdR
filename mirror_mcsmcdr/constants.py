DEFAULT_CONFIG = {
    "MCSManager": {
        "url": "http://127.0.0.1:23333/",
        "uuid": None,
        "remote_uuid": None,
        "apikey": None
    },
    "command": {
        "prefix": "!!mirror",
        "permission": {
            "status": 0,
            "start": 0,
            "stop": 2,
            "kill": 3,
            "sync": 2,
        }
    },
    "display": {
        "server_name": "Mirror"
    },
    "sync": {
        "world": [
            "world"
        ],
        "source": "./server",
        "target": "./Mirror/server",
        "concurrency": 4,
        "ignore_files": [
            "session.lock"
        ]
    },
    "server": {
        "turn_off_auto_save": True,
        "commands": {
            "save_all_worlds": "save-all flush",
            "auto_save_off": "save-off",
            "auto_save_on": "save-on"
        },
        "saved_world_regex": "^Saved the game$",
        "save_world_max_wait_sec": 60
    }
}

TITLE = "MirrorMcsmcdR"
REPLY_TITLE = "§e[MirrorMcsmcdR]§f"
VERSION = "v0.1.0"


