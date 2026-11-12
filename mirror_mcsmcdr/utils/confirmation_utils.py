from threading import Timer
from typing import Callable, Dict, Optional

from mcdreforged.api.all import CommandSource


class ConfirmationTask:
    def __init__(self, action: str, source: CommandSource, callback: Callable[[], object]) -> None:
        self.action = action
        self.source = source
        self.callback = callback
        self.timer: Optional[Timer] = None

    def cancel(self) -> None:
        if self.timer is not None:
            self.timer.cancel()

    def execute(self) -> None:
        self.callback()


class ConfirmationManager:
    """Holds at most one pending confirmation per operator."""

    def __init__(self, on_timeout: Callable[[ConfirmationTask], None]) -> None:
        self.on_timeout = on_timeout
        self.tasks: Dict[str, ConfirmationTask] = {}

    def request(self, operator: str, action: str, source: CommandSource, callback: Callable[[], object], timeout: float) -> None:
        task = ConfirmationTask(action, source, callback)
        task.timer = Timer(timeout, self._timeout, args=(operator,))
        self.tasks[operator] = task
        task.timer.start()

    def _timeout(self, operator: str) -> None:
        task = self.tasks.pop(operator, None)
        if task is not None:
            self.on_timeout(task)

    def cancel(self, operator: str) -> Optional[ConfirmationTask]:
        task = self.tasks.pop(operator, None)
        if task is not None:
            task.cancel()
        return task

    def confirm(self, operator: str) -> Optional[ConfirmationTask]:
        task = self.cancel(operator)
        if task is not None:
            task.execute()
        return task

    def has(self, operator: str) -> bool:
        return operator in self.tasks

    def has_any(self) -> bool:
        return bool(self.tasks)

    def clear(self) -> None:
        for operator in tuple(self.tasks):
            self.cancel(operator)
