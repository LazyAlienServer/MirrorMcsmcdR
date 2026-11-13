from abc import ABC, abstractmethod
from typing import ClassVar

from mirror_mcsmcdr.utils.status import Action, ActionResult, Evidence


class ServerBackend(ABC):
    """One way to reach the server: it reports what it can observe and carries out the actions it supports."""

    supports: ClassVar[frozenset[Action]]

    @abstractmethod
    def observe(self) -> Evidence:
        ...

    @abstractmethod
    def perform(self, result: ActionResult) -> ActionResult:
        """
        Carry out ``result.action``, which is one of :attr:`supports` and has passed :meth:`ActionResult.check`.

        :return: the given result, or a rejection of it if the action could not be carried out
        """
        ...
