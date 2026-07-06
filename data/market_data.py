"""Мультитаймфреймовые снимки рынка с индикаторами."""
from __future__ import annotations
import logging
from indicators.ta import add_indicators

log = logging.getLogger("mdata")


class MarketData:
    def __init__(self, client, cfg: dict):
        self.client = client
        self.tfs: dict = cfg["timeframes"]      # {"trend":"240","main":"60",...}
        self.ind: dict = cfg["indicators"]
        # 600 баров вместо 300: у EMA200 при короткой истории остаётся
        # заметное смещение от стартового значения ewm
        self.history_bars = cfg.get("data", {}).get("history_bars", 600)

    def snapshot(self, symbol: str) -> dict:
        """{"trend": df4h, "main": df1h, "entry": df15, "confirm": df5} с индикаторами."""
        out = {}
        for key, interval in self.tfs.items():
            df = self.client.klines(symbol, interval, limit=self.history_bars)
            if len(df) < self.ind["ema_slow"] + 10:
                raise ValueError(f"{symbol}: мало истории на TF {interval} ({len(df)} свечей)")
            out[key] = add_indicators(df, self.ind)
        return out
