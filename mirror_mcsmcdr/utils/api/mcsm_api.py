import requests, json
from requests import Response
from mirror_mcsmcdr.utils.display_utils import rtr


class MCSManagerApiError(Exception):

    def __init__(self, req: Response) -> None:
        error = json.loads(req.text)
        if "error" in error.keys():
            error = error["error"]
        elif "data" in error.keys():
            error = error["data"]
        super().__init__(rtr(f"mcsm.error.{req.status_code}", title=False, error=error).to_plain_text())


class MCSManagerApi:

    def __init__(self, enable: bool, url: str, uuid: str, remote_uuid: str, apikey: str) -> None:
        self.enable = enable
        self.url = url if url[-1] != "/" else url[:-1]
        self.params = {
            "uuid": uuid,
            "remote_uuid": remote_uuid,
            "apikey": apikey
        }
        self.status_to_text = {
            -1: "unknown",
            0: "stopped",
            1: "stopping",
            2: "starting",
            3: "running"
        }
    
    def _request(self, path: str):
        req : Response = requests.get(url=self.url+path, params=self.params)
        if req.status_code == 200:
            return json.loads(req.text)
        else:
            raise MCSManagerApiError(req)
    
    def status(self):
        return self.status_to_text[self._request("/api/instance")["data"]["status"]]
    
    def start(self):
        self._request("/api/protected_instance/open")
        return "success"
    
    def stop(self):
        self._request("/api/protected_instance/stop")
        return "success"
    
    def kill(self):
        self._request("/api/protected_instance/kill")
        return "success"