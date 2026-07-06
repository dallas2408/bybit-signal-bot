"""Система скоринга: суммирует вклад факторов, применяет пороги."""
from __future__ import annotations
from core.models import Candidate, Signal


class ScoringEngine:
    def __init__(self, cfg: dict):
        s = cfg["scoring"]
        self.min_score = s["min_score"]
        self.min_rr = s["min_rr"]
        self.allow_long = s.get("allow_long", True)
        self.allow_short = s.get("allow_short", True)

    def score(self, cand: Candidate) -> tuple[Signal | None, str | None]:
        if cand.side == "LONG" and not self.allow_long:
            return None, "LONG отключены в конфиге"
        if cand.side == "SHORT" and not self.allow_short:
            return None, "SHORT отключены в конфиге"

        total = sum(c.score for c in cand.components)
        risk = abs(cand.entry - cand.sl)
        if risk <= 0:
            return None, "некорректный SL (risk<=0)"
        rr = abs(cand.tps[1] - cand.entry) / risk  # RR по TP2

        if rr < self.min_rr:
            return None, f"RR {rr:.2f} < минимума {self.min_rr}"
        if total < self.min_score:
            return None, f"рейтинг {total:.1f} < порога {self.min_score}"

        strength = int(round(min(10.0, max(1.0, total))))
        return Signal(
            symbol=cand.symbol, side=cand.side, entry=cand.entry, sl=cand.sl,
            tp1=cand.tps[0], tp2=cand.tps[1], tp3=cand.tps[2],
            rr=round(rr, 2), score=round(total, 1), strength=strength,
            reasons=[c.reason for c in cand.components if c.score > 0],
            strategy=cand.strategy,
        ), None
