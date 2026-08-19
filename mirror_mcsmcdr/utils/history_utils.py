import json
import os
from pathlib import Path
from threading import Lock
from typing import Any


class SyncHistory:
    
    def __init__(self, path: Path, max_count: int) -> None:
        if type(max_count) is not int or max_count < -1:
            raise ValueError("max_history_count must be -1 or a non-negative integer")
        self.path = path
        self.max_count = max_count
        self.lock = Lock()


    def read(self) -> list[dict[str, Any]]:
        with self.lock:
            return self._read_unlocked()

    def append(self, record: dict[str, Any]) -> None:
        if self.max_count == 0:
            return
        with self.lock:
            history = [record, *self._read_unlocked()]
            if self.max_count != -1:
                history = history[:self.max_count]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(".json.tmp")
            with temp_path.open("w", encoding="utf-8") as file:
                json.dump(history, file, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.path)

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as file:
                history = json.load(file)
            return history if isinstance(history, list) else []
        except (OSError, json.JSONDecodeError):
            broken_path = self.path.with_suffix(".json.broken")
            try:
                os.replace(self.path, broken_path)
            except OSError:
                pass
            return []
