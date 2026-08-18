from enum import Enum


class ServerStatus(str, Enum):
    UNKNOWN = "unknown"
    STOPPED = "stopped"
    STOPPING = "stopping"
    STARTING = "starting"
    RUNNING = "running"
    DETACHED_JAVA = "detached_java"
    DETACHED_SCREEN = "detached_screen"
    RCON_STATUS_MISMATCH = "rcon_status_mismatch"
    UNAVAILABLE = "unavailable"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def is_available(cls, status: "ServerStatus") -> bool:
        return type(status) is cls and status in {
            cls.UNKNOWN,
            cls.STOPPED,
            cls.STOPPING,
            cls.STARTING,
            cls.RUNNING,
            cls.DETACHED_JAVA,
            cls.DETACHED_SCREEN,
        }
