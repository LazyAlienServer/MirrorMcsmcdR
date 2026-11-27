import json
from typing import Any

import requests
from mcdreforged.api.all import ServerInterface
from requests import Response

from mirror_mcsmcdr.config.proxy_config import MCSMConfig
from mirror_mcsmcdr.server.action import Action, ActionResult
from mirror_mcsmcdr.server.backend.base import ServerBackend
from mirror_mcsmcdr.server.status import Evidence, ServerState


class MCSManagerProxyError(Exception):

    def __init__(self, req: Response) -> None:
        error = json.loads(req.text)
        if "error" in error.keys():
            error = error["error"]
        elif "data" in error.keys():
            error = error["data"]
        super().__init__(ServerInterface.si().rtr(f"mirror_mcsmcdr.mcsm.error.{req.status_code}", error=error).to_plain_text())


class MCSManagerProxy(ServerBackend):
    supports = frozenset({Action.START, Action.STOP, Action.KILL})

    _PANEL_STATES = {
        -1: ServerState.UNKNOWN,
        0: ServerState.STOPPED,
        1: ServerState.STOPPING,
        2: ServerState.STARTING,
        3: ServerState.RUNNING,
    }
    # seconds a request may take; without a limit, a panel that stops answering would hold up whoever waits on it
    _REQUEST_TIMEOUT = 10

    def __init__(self, config: MCSMConfig) -> None:
        self.url = config.url.rstrip("/")
        self.params = {"uuid": config.uuid, "remote_uuid": config.remote_uuid, "apikey": config.apikey}

    def _request(self, path: str) -> Any:
        req: Response = requests.get(url=self.url + path, params=self.params, timeout=self._REQUEST_TIMEOUT)
        if req.status_code != 200:
            raise MCSManagerProxyError(req)
        return json.loads(req.text)

    def observe(self) -> Evidence:
        return Evidence(panel_state=self._PANEL_STATES[self._request("/api/instance")["data"]["status"]])

    def _start(self, result: ActionResult) -> ActionResult:
        self._request("/api/protected_instance/open")
        return result

    def _stop(self, result: ActionResult) -> ActionResult:
        self._request("/api/protected_instance/stop")
        return result

    def _kill(self, result: ActionResult) -> ActionResult:
        self._request("/api/protected_instance/kill")
        return result
