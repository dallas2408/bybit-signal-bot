"""Технические индикаторы (pandas/numpy, без внешних TA-библиотек)."""
from __future__ import annotations
import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI по Уайлдеру."""
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    out = out.where(~((dn == 0) & (up > 0)), 100.0)   # только рост -> 100
    out = out.where(~((up == 0) & (dn > 0)), 0.0)     # только падение -> 0
    return out.fillna(50.0)


def macd(close: pd.Series, fast=12, slow=26, signal=9):
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR по Уайлдеру."""
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def add_indicators(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = ema(df["close"], p["ema_fast"])
    df["ema_mid"] = ema(df["close"], p["ema_mid"])
    df["ema_slow"] = ema(df["close"], p["ema_slow"])
    df["rsi"] = rsi(df["close"], p["rsi_period"])
    df["macd"], df["macd_sig"], df["macd_hist"] = macd(
        df["close"], p["macd_fast"], p["macd_slow"], p["macd_signal"])
    df["atr"] = atr(df, p["atr_period"])
    df["vol_sma"] = df["volume"].rolling(p["vol_sma"]).mean()
    return df
