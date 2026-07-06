"""Модели данных: компоненты скоринга, кандидаты, сигналы."""
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field, asdict


@dataclass
class Component:
    """Один фактор скоринга: имя, вклад в оценку, причина."""
    name: str
    score: float
    reason: str


@dataclass
class Candidate:
    """Кандидат в сигнал от стратегии (до скоринга)."""
    symbol: str
    side: str                  # LONG | SHORT
    entry: float
    sl: float
    tps: list[float]
    components: list[Component]
    strategy: str


@dataclass
class Signal:
    """Опубликованный сигнал."""
    symbol: str
    side: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    rr: float
    score: float
    strength: int              # 1..10
    reasons: list[str]
    strategy: str
    created_at: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: str = "ACTIVE"     # ACTIVE|TP1|TP2|TP3|SL|CANCELLED
    hit: list[str] = field(default_factory=list)
    sl_current: float | None = None
    message_id: int | None = None
    closed_at: float | None = None

    def __post_init__(self):
        if self.sl_current is None:
            self.sl_current = self.sl

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Signal":
        return cls(**d)
