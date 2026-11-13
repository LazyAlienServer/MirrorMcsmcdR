from abc import ABC, abstractmethod
from typing import ClassVar

from mirror_mcsmcdr.server.status import Action, ActionResult, Evidence


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
