"""Рыночная структура: свинги, HH/HL/LH/LL, ближайшие уровни."""
from __future__ import annotations
import pandas as pd


def swings(df: pd.DataFrame, k: int = 3):
    """Фрактальные свинги. Возвращает списки (index, price)."""
    h = df["high"].values
    l = df["low"].values
    highs, lows = [], []
    for i in range(k, len(df) - k):
        if h[i] == max(h[i - k:i + k + 1]):
            highs.append((i, float(h[i])))
        if l[i] == min(l[i - k:i + k + 1]):
            lows.append((i, float(l[i])))
    return highs, lows


def market_structure(df: pd.DataFrame, k: int = 3):
    """'bull' (HH+HL) | 'bear' (LH+LL) | 'mixed' | 'unknown'."""
    hs, ls = swings(df, k)
    if len(hs) < 2 or len(ls) < 2:
        return "unknown", hs, ls
    hh = hs[-1][1] > hs[-2][1]
    hl = ls[-1][1] > ls[-2][1]
    if hh and hl:
        return "bull", hs, ls
    if (not hh) and (not hl):
        return "bear", hs, ls
    return "mixed", hs, ls
