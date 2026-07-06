"""Клиент публичного API Bybit v5 (linear perpetual). Ключи не нужны."""
from __future__ import annotations
import time
import logging
import requests
import pandas as pd

log = logging.getLogger("bybit")
BASE = "https://api.bybit.com"


class BybitError(Exception):
    pass


class BybitClient:
    def __init__(self, timeout: int = 10, max_retries: int = 3, backoff: float = 1.5):
        self.s = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.consecutive_failures = 0

    def _get(self, path: str, params: dict) -> dict:
        last_err = None
        for attempt in range(self.max_retries):
            try:
                r = self.s.get(BASE + path, params=params, timeout=self.timeout)
                data = r.json()
                if data.get("retCode") == 0:
                    self.consecutive_failures = 0
                    return data["result"]
                last_err = BybitError(f"{path}: retCode={data.get('retCode')} {data.get('retMsg')}")
            except Exception as e:  # сеть/json
                last_err = e
            time.sleep(self.backoff * (attempt + 1))
        self.consecutive_failures += 1
        raise BybitError(f"Bybit API fail after {self.max_retries} retries: {last_err}")

    def tickers(self) -> list[dict]:
        return self._get("/v5/market/tickers", {"category": "linear"})["list"]

    def klines(self, symbol: str, interval: str, limit: int = 300,
               end: int | None = None, drop_forming: bool = True) -> pd.DataFrame:
        """Свечи, отсортированы по возрастанию времени. ts = время открытия (мс)."""
        params = {"category": "linear", "symbol": symbol, "interval": interval, "limit": min(limit, 1000)}
        if end:
            params["end"] = end
        rows = self._get("/v5/market/kline", params)["list"]  # новые первыми
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "turnover"])
        df = df.astype(float)
        df["ts"] = df["ts"].astype("int64")
        df = df.iloc[::-1].reset_index(drop=True)
        if drop_forming and len(df) > 1 and end is None:
            df = df.iloc[:-1].reset_index(drop=True)  # незакрытая свеча — вон
        return df

    def open_interest(self, symbol: str, interval: str = "1h", limit: int = 12) -> list[dict]:
        res = self._get("/v5/market/open-interest",
                        {"category": "linear", "symbol": symbol,
                         "intervalTime": interval, "limit": limit})
        return res.get("list", [])  # новые первыми

    def oi_change_pct(self, symbol: str, hours: int = 4) -> float | None:
        try:
            rows = self.open_interest(symbol, "1h", hours + 1)
            if len(rows) < 2:
                return None
            new = float(rows[0]["openInterest"])
            old = float(rows[-1]["openInterest"])
            if old <= 0:
                return None
            return (new - old) / old * 100.0
        except Exception as e:
            log.debug("OI fetch fail %s: %s", symbol, e)
            return None
