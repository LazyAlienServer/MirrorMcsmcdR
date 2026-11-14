from abc import ABC, abstractmethod
from typing import ClassVar

from mirror_mcsmcdr.config.proxy_config import TerminalConfig
from mirror_mcsmcdr.server.action import Action, ActionResult
from mirror_mcsmcdr.server.status import Evidence


class ServerBackend(ABC):
    """One way to reach the server: it reports what it can observe and carries out the actions it supports."""

    supports: ClassVar[frozenset[Action]]

    @abstractmethod
    def observe(self) -> Evidence:
        ...

    def perform(self, result: ActionResult) -> ActionResult:
        """
        Carry out ``result.action``, which is one of :attr:`supports` and has passed :meth:`ActionResult.check`.

        :return: the given result, or a rejection of it if the action could not be carried out
        """
        match result.action:
            case Action.START:
                return self._start(result)
            case Action.STOP:
                return self._stop(result)
            case Action.KILL:
                return self._kill(result)
            case Action.FORCEKILL:
                return self._forcekill(result)

    # A backend overrides the methods of the actions it lists in :attr:`supports`; the others are never called.

    def _start(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _stop(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _kill(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _forcekill(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _unsupported(self, result: ActionResult) -> NotImplementedError:
        return NotImplementedError(f"{type(self).__name__} does not support {result.action}")


class TerminalProxy(ServerBackend, ABC):
    """A backend that launches the server from a command line on this machine."""

    def __init__(self, config: TerminalConfig) -> None:
        self.terminal_name = config.terminal_name or "Mirror"
        self.path = config.launch_path
        self.command = config.launch_command
        self.is_mcdr = config.is_mcdr

    @property
    def stop_command(self) -> str:
        return "!!MCDR server stop_exit" if self.is_mcdr else "stop"
