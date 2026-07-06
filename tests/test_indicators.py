import numpy as np
import pandas as pd
from indicators.ta import ema, rsi, atr, add_indicators

P = dict(ema_fast=5, ema_mid=10, ema_slow=20, rsi_period=14,
         macd_fast=12, macd_slow=26, macd_signal=9, atr_period=14, vol_sma=5)


def _df(n=200, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.1, 1, n)
    low = close - rng.uniform(0.1, 1, n)
    return pd.DataFrame({"ts": np.arange(n), "open": close, "high": high,
                         "low": low, "close": close, "volume": rng.uniform(1, 10, n),
                         "turnover": np.ones(n)})


def test_rsi_bounds():
    df = _df()
    r = rsi(df["close"])
    assert r.between(0, 100).all()


def test_rsi_extremes():
    up = pd.Series(np.arange(1, 100, dtype=float))
    assert rsi(up).iloc[-1] > 90
    assert rsi(up[::-1].reset_index(drop=True)).iloc[-1] < 10


def test_atr_positive():
    df = _df()
    assert (atr(df).dropna() > 0).all()


def test_ema_converges():
    s = pd.Series([10.0] * 100)
    assert abs(ema(s, 5).iloc[-1] - 10.0) < 1e-9


def test_add_indicators_columns():
    df = add_indicators(_df(), P)
    for col in ["ema_fast", "ema_mid", "ema_slow", "rsi", "macd_hist", "atr", "vol_sma"]:
        assert col in df.columns
