import requests, json
from requests import Response
from mirror_mcsmcdr.utils.display_utils import rtr
from abc import ABC, abstractmethod

class HTTPProxyError(Exception):

    def __init__(self, req: Response) -> None:
        super().__init__("HTTPProxyError")

class AbstractHTTPProxy(ABC):

    def __init__(self, enable: bool, url: str, *args, **kwargs) -> None:
        self.enable = enable
        self.url = url if url[-1] != "/" else url[:-1]
        self.params = kwargs
        self.status_to_text = {
            -1: "unknown",
            0: "stopped",
            1: "stopping",
            2: "starting",
            3: "running"
        }
    
    def _request(self, path: str, exception: type = HTTPProxyError):
        req : Response = requests.get(url=self.url+path, params=self.params)
        if req.status_code == 200:
            return json.loads(req.text)
        else:
            raise exception(req)
    
    @abstractmethod
    def status(self) -> str:
        ...
    
    @abstractmethod
    def start(self) -> str:
        return "success"
    
    @abstractmethod
    def stop(self) -> str:
        return "success"
    
    @abstractmethod
    def kill(self) -> str:
        return "success"

class MCSManagerProxyError(Exception):

    def __init__(self, req: Response) -> None:
        error = json.loads(req.text)
        if "error" in error.keys():
            error = error["error"]
        elif "data" in error.keys():
            error = error["data"]
        super().__init__(rtr(f"mcsm.error.{req.status_code}", title=False, error=error).to_plain_text())


class MCSManagerProxy(AbstractHTTPProxy):

    def __init__(self, enable: bool, url: str, uuid: str, remote_uuid: str, apikey: str) -> None:
        super().__init__(enable, url, uuid = uuid, remote_uuid = remote_uuid, apikey = apikey)
    
    def _request(self, path: str, exception: type = MCSManagerProxyError):
        return super()._request(path, exception)
    
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