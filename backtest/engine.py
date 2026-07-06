"""Бэктест v1: база 15M, ресемплинг в 1H/4H, тот же код стратегии, что и live.

Особенности и честные допущения:
  - вход по close 15M-свечи сигнала;
  - если SL и TP в одной свече — засчитывается SL (консервативно);
  - 5M-подтверждение по умолчанию выключено (base TF = 15M);
  - funding/OI истории нет — эти факторы в бэктесте не начисляются
    (реальный live-скор будет чуть выше, порог min_score применяется как есть);
  - результат в R: закрытие долями exit_weights на TP1/TP2/TP3,
    после TP1 стоп в безубыток (если включено в конфиге).

Запуск:
  python -m backtest.engine --symbols BTCUSDT ETHUSDT --months 12
"""
from __future__ import annotations
import argparse
import json
import logging
import time

import numpy as np
import pandas as pd

from core.config import load_config
from core.registry import build_strategies
from data.bybit_client import BybitClient
from indicators.ta import add_indicators
from analysis import regime as regime_mod
from scoring.engine import ScoringEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backtest")

MS_15M = 15 * 60 * 1000


def fetch_history(client: BybitClient, symbol: str, months: int) -> pd.DataFrame:
    """Пагинация 15M-свечей назад от текущего момента."""
    end = int(time.time() * 1000)
    start = end - months * 30 * 24 * 3600 * 1000
    chunks = []
    cursor = end
    while cursor > start:
        df = client.klines(symbol, "15", limit=1000, end=cursor, drop_forming=False)
        if df.empty:
            break
        chunks.append(df)
        oldest = int(df["ts"].iloc[0])
        if oldest >= cursor:
            break
        cursor = oldest - 1
        time.sleep(0.15)
    full = pd.concat(chunks).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    full = full[full["ts"] >= start].reset_index(drop=True)
    return full.iloc[:-1]  # без формирующейся


def resample(df15: pd.DataFrame, minutes: int, ind: dict) -> pd.DataFrame:
    d = df15.copy()
    d["dt"] = pd.to_datetime(d["ts"], unit="ms")
    r = d.set_index("dt").resample(f"{minutes}min").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"), ts=("ts", "first"),
    ).dropna().reset_index(drop=True)
    r["close_ts"] = r["ts"] + minutes * 60 * 1000  # время закрытия бара
    return add_indicators(r, ind)


def run_symbol(symbol: str, months: int, cfg: dict, client: BybitClient) -> list[dict]:
    ind = cfg["indicators"]
    strategies = build_strategies(cfg)
    scoring = ScoringEngine(cfg)
    bt = cfg["backtest"]
    exit_w = bt["exit_weights"]
    move_be = cfg["signals"].get("move_sl_to_breakeven_after_tp1", True)
    max_hold_bars = int(cfg["signals"]["max_hold_hours"] * 60 / 15)
    cooldown_bars = max(1, int(cfg["signals"]["cooldown_minutes"] / 15))
    # комиссии (тейкер, обе стороны) + проскальзывание, % от нотионала
    cost_pct = 2 * bt.get("fee_pct_per_side", 0.055) + bt.get("slippage_pct", 0.03)

    log.info("%s: загрузка истории (%d мес)...", symbol, months)
    df15 = add_indicators(fetch_history(client, symbol, months), ind)
    df15["close_ts"] = df15["ts"] + MS_15M
    df1h = resample(df15, 60, ind)
    df4h = resample(df15, 240, ind)
    log.info("%s: %d свечей 15M", symbol, len(df15))

    warmup = ind["ema_slow"] + 20   # требуется на каждом TF отдельно
    c1 = df1h["close_ts"].values
    c4 = df4h["close_ts"].values
    trades = []
    i = warmup
    n = len(df15)
    if len(df4h) <= warmup:
        log.warning("%s: истории мало даже для прогрева EMA200 на 4H "
                    "(%d баров, нужно >%d) — увеличь --months",
                    symbol, len(df4h), warmup)
        return []
    while i < n - 1:
        t = int(df15["close_ts"].iloc[i])
        j1 = int(np.searchsorted(c1, t, side="right"))
        j4 = int(np.searchsorted(c4, t, side="right"))
        if j1 < warmup or j4 < warmup:
            i += 1
            continue
        snap = {
            "trend": df4h.iloc[:j4].tail(250),
            "main": df1h.iloc[:j1].tail(250),
            "entry": df15.iloc[:i + 1].tail(250),
        }
        if bt.get("use_confirm_tf"):
            snap["confirm"] = snap["entry"]

        reg = regime_mod.detect(snap["main"], cfg["regime"])
        if reg["regime"] == "flat":
            i += 1
            continue

        entry_price = float(df15["close"].iloc[i])
        ctx = {"symbol": symbol, "last_price": entry_price,
               "funding": None, "oi_change_pct": None}

        published = None
        for strat in strategies:
            cand, _ = strat.evaluate(snap, ctx)
            if cand is None:
                continue
            sig, _ = scoring.score(cand)
            if sig is not None:
                published = sig
                break
        if published is None:
            i += 1
            continue

        # --- симуляция сделки по будущим 15M-барам ---
        s = published
        sgn = 1 if s.side == "LONG" else -1
        sl = s.sl
        risk = abs(s.entry - sl)
        remaining = 1.0
        realized_r = 0.0
        hit = []
        outcome = "TIMEOUT"
        exit_k = min(i + max_hold_bars, n - 1)
        for k in range(i + 1, min(i + 1 + max_hold_bars, n)):
            hi, lo = float(df15["high"].iloc[k]), float(df15["low"].iloc[k])
            # консервативно: сначала стоп
            stop_hit = lo <= sl if sgn > 0 else hi >= sl
            if stop_hit:
                r_at_stop = sgn * (sl - s.entry) / risk
                realized_r += remaining * r_at_stop
                remaining = 0.0
                outcome = "SL" if not hit else f"BE_after_{hit[-1]}"
                exit_k = k
                break
            for w, lvl, tp in zip(exit_w, ("TP1", "TP2", "TP3"), (s.tp1, s.tp2, s.tp3)):
                if lvl in hit:
                    continue
                tp_hit = hi >= tp if sgn > 0 else lo <= tp
                if tp_hit:
                    hit.append(lvl)
                    realized_r += w * sgn * (tp - s.entry) / risk
                    remaining -= w
                    if lvl == "TP1" and move_be:
                        sl = s.entry
            if "TP3" in hit:
                outcome = "TP3"
                remaining = 0.0
                exit_k = k
                break
        if remaining > 0:  # таймаут — закрытие по рынку
            last_close = float(df15["close"].iloc[exit_k])
            realized_r += remaining * sgn * (last_close - s.entry) / risk
        # издержки: комиссии на круг + проскальзывание, в единицах R
        realized_r -= (cost_pct / 100.0) * s.entry / risk
        trades.append({"symbol": symbol, "side": s.side, "score": s.score,
                       "rr_plan": s.rr, "r": round(realized_r, 3),
                       "outcome": outcome if outcome != "TIMEOUT" or hit == [] else f"TIMEOUT_{hit[-1]}",
                       "ts": int(df15["ts"].iloc[i])})
        # следующий поиск строго ПОСЛЕ выхода из сделки + cooldown:
        # перекрывающихся сделок по одной монете нет (как в live)
        i = exit_k + cooldown_bars
    return trades


def report(trades: list[dict]) -> dict:
    if not trades:
        return {"trades": 0, "note": "сигналов не найдено — ослабь min_score или расширь период"}
    r = np.array([t["r"] for t in trades])
    wins, losses = r[r > 0], r[r <= 0]
    eq = np.cumsum(r)
    dd = float(np.max(np.maximum.accumulate(eq) - eq)) if len(eq) else 0.0
    def wr(side):
        rs = [t["r"] for t in trades if t["side"] == side]
        return round(100 * sum(1 for x in rs if x > 0) / len(rs), 1) if rs else None
    return {
        "trades": len(trades),
        "win_rate_pct": round(100 * len(wins) / len(r), 1),
        "profit_factor": round(float(wins.sum() / abs(losses.sum())), 2) if losses.sum() != 0 else float("inf"),
        "total_R": round(float(r.sum()), 2),
        "avg_R": round(float(r.mean()), 3),
        "max_drawdown_R": round(dd, 2),
        "avg_planned_RR": round(float(np.mean([t["rr_plan"] for t in trades])), 2),
        "long_win_rate_pct": wr("LONG"),
        "short_win_rate_pct": wr("SHORT"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=["BTCUSDT"])
    ap.add_argument("--months", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config()
    months = args.months or cfg["backtest"]["months"]
    client = BybitClient()
    all_trades = []
    for sym in args.symbols:
        try:
            all_trades += run_symbol(sym, months, cfg, client)
        except Exception as e:
            log.error("%s: %s", sym, e)

    rep = report(all_trades)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    with open("state/backtest_report.json", "w", encoding="utf-8") as f:
        json.dump({"report": rep, "trades": all_trades}, f, ensure_ascii=False, indent=1)
    log.info("Отчёт сохранён: state/backtest_report.json")


if __name__ == "__main__":
    main()
