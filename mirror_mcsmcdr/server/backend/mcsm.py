import json
from typing import Any

import requests
from requests import Response

from mirror_mcsmcdr.config.proxy_config import MCSMConfig
from mirror_mcsmcdr.text import rtr
from mirror_mcsmcdr.server.backend.base import ServerBackend
from mirror_mcsmcdr.server.status import Action, ActionResult, Evidence, ServerState


class MCSManagerProxyError(Exception):

    def __init__(self, req: Response) -> None:
        error = json.loads(req.text)
        if "error" in error.keys():
            error = error["error"]
        elif "data" in error.keys():
            error = error["data"]
        super().__init__(rtr(f"mcsm.error.{req.status_code}", title=False, error=error).to_plain_text())


class MCSManagerProxy(ServerBackend):
    supports = frozenset({Action.START, Action.STOP, Action.KILL})

    _PANEL_STATES = {
        -1: ServerState.UNKNOWN,
        0: ServerState.STOPPED,
        1: ServerState.STOPPING,
        2: ServerState.STARTING,
        3: ServerState.RUNNING,
    }
    _ENDPOINTS = {
        Action.START: "/api/protected_instance/open",
        Action.STOP: "/api/protected_instance/stop",
        Action.KILL: "/api/protected_instance/kill",
    }

    def __init__(self, config: MCSMConfig) -> None:
        self.url = config.url.rstrip("/")
        self.params = {"uuid": config.uuid, "remote_uuid": config.remote_uuid, "apikey": config.apikey}

    def _request(self, path: str) -> Any:
        req: Response = requests.get(url=self.url + path, params=self.params)
        if req.status_code != 200:
            raise MCSManagerProxyError(req)
        return json.loads(req.text)

    def observe(self) -> Evidence:
        return Evidence(panel_state=self._PANEL_STATES[self._request("/api/instance")["data"]["status"]])

    def perform(self, result: ActionResult) -> ActionResult:
        self._request(self._ENDPOINTS[result.action])
        return result
