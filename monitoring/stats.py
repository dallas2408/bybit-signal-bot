"""Статистика paper trading из state/history.jsonl.
Запуск: python -m monitoring.stats
Считает реализованный R каждой закрытой сделки по тем же exit_weights,
что и бэктест, и печатает отчёт в том же формате (Win Rate, PF, MaxDD и т.д.).
"""
from __future__ import annotations
import json
import os

from core.config import load_config
from backtest.engine import report

HISTORY_FILE = "state/history.jsonl"
FINAL_EVENTS = ("SL", "BE", "TP3", "CANCELLED")


def collect_trades(path: str = HISTORY_FILE) -> list[dict]:
    cfg = load_config()
    w = cfg["backtest"]["exit_weights"]
    opens: dict[str, dict] = {}
    trades = []
    if not os.path.exists(path):
        return trades
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("event") == "OPEN":
                opens[e["id"]] = e
            elif e.get("event") in FINAL_EVENTS:
                o = opens.get(e["id"], e)
                risk = abs(o["entry"] - o["sl"])
                if risk <= 0:
                    continue
                sgn = 1 if o["side"] == "LONG" else -1
                tps = [o["tp1"], o["tp2"], o["tp3"]]
                hit = e.get("hit", [])
                r, rem = 0.0, 1.0
                for wt, lvl, tp in zip(w, ("TP1", "TP2", "TP3"), tps):
                    if lvl in hit:
                        r += wt * sgn * (tp - o["entry"]) / risk
                        rem -= wt
                if rem > 1e-9:
                    px = e.get("close_px")
                    if px is None:
                        px = o["sl"] if e["event"] == "SL" else o["entry"]
                    r += rem * sgn * (px - o["entry"]) / risk
                trades.append({"symbol": o["symbol"], "side": o["side"],
                               "r": round(r, 3), "rr_plan": o.get("rr", 0),
                               "outcome": e["event"], "ts": e.get("ts")})
    return trades


if __name__ == "__main__":
    trades = collect_trades()
    print(json.dumps(report(trades), ensure_ascii=False, indent=2))
