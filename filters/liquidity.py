"""Фильтр ликвидности: отбор торговой вселенной из тикеров Bybit."""
from __future__ import annotations
import logging

log = logging.getLogger("universe")


def ticker_metrics(t: dict) -> dict:
    last = float(t.get("lastPrice") or 0)
    bid = float(t.get("bid1Price") or 0)
    ask = float(t.get("ask1Price") or 0)
    spread_pct = ((ask - bid) / last * 100) if (last > 0 and bid > 0 and ask > 0) else 999.0
    oi_val = float(t.get("openInterestValue") or 0)
    if oi_val == 0:
        oi_val = float(t.get("openInterest") or 0) * last
    return {
        "symbol": t["symbol"],
        "last_price": last,
        "turnover24h": float(t.get("turnover24h") or 0),
        "oi_usd": oi_val,
        "spread_pct": spread_pct,
        "funding": float(t.get("fundingRate") or 0),
    }


def build_universe(tickers: list[dict], cfg: dict) -> list[str]:
    u = cfg["universe"]
    if u["mode"] == "manual":
        return list(u["manual_symbols"])
    rows = []
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT") or sym in u.get("exclude", []):
            continue
        m = ticker_metrics(t)
        if m["turnover24h"] < u["min_volume_24h_usd"]:
            continue
        if m["oi_usd"] < u["min_open_interest_usd"]:
            continue
        if m["spread_pct"] > u["max_spread_pct"]:
            continue
        rows.append(m)
    rows.sort(key=lambda r: r["turnover24h"], reverse=True)
    universe = [r["symbol"] for r in rows[:u["top_n"]]]
    log.info("Вселенная: %d пар (top по обороту): %s", len(universe), ", ".join(universe[:10]) + "...")
    return universe
