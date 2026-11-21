import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Optional


class SyncStatus(str, Enum):
    SUCCESS = "success"
    IDENTICAL = "identical"
    FAILED = "failed"


@dataclass(frozen=True)
class SyncRecord:
    time: str
    operator: str
    status: SyncStatus
    duration: Optional[str] = None
    changed_files_count: int = 0
    paths_notfound: list[str] = field(default_factory=list)
    exception: Optional[str] = None
    # the pre-sync backup made by the mirror's PrimeBackup, whatever became of the sync afterwards
    backup_id: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        detail: dict[str, Any]
        if self.status == SyncStatus.FAILED:
            detail = {"exception": self.exception}
        else:
            detail = {
                "duration": self.duration,
                "changed_files_count": self.changed_files_count,
                "paths_notfound": self.paths_notfound,
            }
        data: dict[str, Any] = {
            "time": self.time,
            "operator": self.operator,
            "status": self.status.value,
            "detail": detail,
        }
        if self.backup_id is not None:
            data["backup_id"] = self.backup_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncRecord":
        detail = data.get("detail", {})
        backup_id = data.get("backup_id")
        if backup_id is not None and type(backup_id) is not int:
            raise ValueError("backup_id must be an integer")
        return cls(
            time=data["time"],
            operator=data["operator"],
            status=SyncStatus(data["status"]),
            duration=detail.get("duration"),
            changed_files_count=detail.get("changed_files_count", 0),
            paths_notfound=detail.get("paths_notfound", []),
            exception=detail.get("exception"),
            backup_id=backup_id,
        )


class SyncHistory:

    def __init__(self, path: Path, max_count: int) -> None:
        if type(max_count) is not int or max_count < -1:
            raise ValueError("max_history_count must be -1 or a non-negative integer")
        self.path = path
        self.max_count = max_count
        self.lock = Lock()

    def read(self) -> list[SyncRecord]:
        """Return stored records, newest first; entries that cannot be parsed are skipped."""
        with self.lock:
            entries = self._read_unlocked()
        records = []
        for entry in entries:
            try:
                records.append(SyncRecord.from_dict(entry))
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
        return records

    def append(self, record: SyncRecord) -> None:
        if self.max_count == 0:
            return
        with self.lock:
            history = [record.to_dict(), *self._read_unlocked()]
            if self.max_count != -1:
                history = history[:self.max_count]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(".json.tmp")
            with temp_path.open("w", encoding="utf-8") as file:
                json.dump(history, file, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.path)

    def _read_unlocked(self) -> list[Any]:
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
