"""Состояние рынка: тренд / флэт / волатильность (обычно по 1H)."""
from __future__ import annotations
import pandas as pd


def detect(df: pd.DataFrame, params: dict) -> dict:
    row = df.iloc[-1]
    a = float(row["atr"]) if row["atr"] > 0 else 1e-12
    atr_pct = a / float(row["close"])
    sep = abs(float(row["ema_fast"]) - float(row["ema_slow"])) / a
    if sep < params.get("flat_sep_atr", 1.0):
        regime = "flat"
    elif row["ema_fast"] > row["ema_mid"] > row["ema_slow"] and row["close"] > row["ema_slow"]:
        regime = "trend_up"
    elif row["ema_fast"] < row["ema_mid"] < row["ema_slow"] and row["close"] < row["ema_slow"]:
        regime = "trend_down"
    else:
        regime = "mixed"
    vol = "high" if atr_pct > params.get("high_vol_atr_pct", 0.03) else "normal"
    return {"regime": regime, "vol": vol, "atr_pct": atr_pct}
