"""Базовый класс стратегии. Новая стратегия = новый файл + @register_strategy."""
from __future__ import annotations
from abc import ABC, abstractmethod
from core.models import Candidate


class BaseStrategy(ABC):
    name: str = "base"

    def __init__(self, params: dict, weight: float = 1.0):
        self.params = params
        self.weight = weight

    @abstractmethod
    def evaluate(self, snapshot: dict, ctx: dict) -> tuple[Candidate | None, str | None]:
        """snapshot: {"trend": df4h, "main": df1h, "entry": df15, "confirm": df5}
        ctx: {"last_price", "funding", "oi_change_pct", ...}
        Возвращает (кандидат, None) или (None, причина_отказа)."""
        ...
