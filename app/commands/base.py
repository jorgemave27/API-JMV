from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TCommand = TypeVar("TCommand")
TResult = TypeVar("TResult")


class CommandHandler(ABC, Generic[TCommand, TResult]):
    """
    Contrato base para handlers de comandos (escrituras).
    """

    @abstractmethod
    def handle(self, command: TCommand) -> TResult:
        raise NotImplementedError
