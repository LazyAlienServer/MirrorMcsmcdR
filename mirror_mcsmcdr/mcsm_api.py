import requests, json
from requests import Response


class MCSManagerApiError(Exception):

    def __init__(self, req: Response) -> None:
        match req.status_code:
            case 400:
                super().__init__("[400] 请求参数错误, 请尝试前往GitHub提交issue以解决 (%s)"%req)
            case 403:
                super().__init__("[403] 权限不足, 请回报服务器管理员(%s)"%req)
            case 500:
                super().__init__("[500] 未知的服务器内部错误(%s)"%req)


class MCSManagerApi:

    def __init__(self, url: str, uuid: str, remote_uuid: str, apikey: str) -> None:
        self.url = url if url[-1] != "/" else url[:-1]
        self.params = {
            "uuid": uuid,
            "remote_uuid": remote_uuid,
            "apikey": apikey
        }
        self.status_to_text = {
            -1: "状态未知",
            0: "已停止",
            1: "正在停止",
            2: "正在启动",
            3: "正在运行"
        }
    
    def _request(self, path: str):
        req : Response = requests.get(url=self.url+path, params=self.params)
        if req.status_code == 200:
            return json.loads(req.text)
        else:
            raise MCSManagerApiError(req)
    
    def status(self):
        "-1:状态未知; 0:已停止; 1:正在停止; 2:正在启动; 3:正在运行"
        return self._request("/api/instance")["data"]["status"]
    
    def start(self):
        return self._request("/api/protected_instance/open")
    
    def stop(self):
        return self._request("/api/protected_instance/stop")
    
    def restart(self):
        return self._request("/api/protected_instance/restart")
    
    def kill(self):
        return self._request("/api/protected_instance/kill")
