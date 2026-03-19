from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TQuery = TypeVar("TQuery")
TResult = TypeVar("TResult")


class QueryHandler(ABC, Generic[TQuery, TResult]):
    """
    Contrato base para handlers de consultas (lecturas).
    """

    @abstractmethod
    def handle(self, query: TQuery) -> TResult:
        raise NotImplementedError
