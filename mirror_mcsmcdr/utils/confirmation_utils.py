from mcdreforged.api.all import CommandSource, CommandContext
from typing import Any, Callable, Dict, Optional
from threading import Timer

class ConfirmationTask:
    def __init__(
        self,
        action: str,
        source: CommandSource,
        context: CommandContext,
        callback: Callable[..., Any],
        callback_args: tuple,
        callback_kwargs: dict,
    ) -> None:
        self.action = action
        self.source = source
        self.context = context
        self.callback = callback
        self.callback_args = callback_args
        self.callback_kwargs = callback_kwargs
        self.timer: Optional[Timer] = None

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()

    def execute(self):
        return self.callback(*self.callback_args, **self.callback_kwargs)


class ConfirmationManager:
    def __init__(self, timeout: float, on_timeout: Callable[[ConfirmationTask], None]) -> None:
        self.timeout = timeout
        self.on_timeout = on_timeout
        self.tasks: Dict[str, ConfirmationTask] = {}

    def request(
        self,
        operator: str,
        action: str,
        source: CommandSource,
        context: CommandContext,
        callback: Callable[..., Any],
        callback_args: tuple,
        callback_kwargs: dict,
    ):
        task = ConfirmationTask(
            action,
            source,
            context,
            callback,
            callback_args,
            callback_kwargs,
        )
        task.timer = Timer(self.timeout, self._timeout, args=(operator,))
        self.tasks[operator] = task
        task.timer.start()

    def _timeout(self, operator: str):
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

    def clear(self):
        for operator in tuple(self.tasks):
            self.cancel(operator)