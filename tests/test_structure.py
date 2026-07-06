import numpy as np
import pandas as pd
from analysis.structure import market_structure


def _trend(up=True, n=120):
    base = np.linspace(0, 20, n) * (1 if up else -1)
    wave = 2 * np.sin(np.linspace(0, 12 * np.pi, n))
    close = 100 + base + wave
    return pd.DataFrame({"high": close + 0.5, "low": close - 0.5, "close": close})


def test_bull():
    ms, hs, ls = market_structure(_trend(True))
    assert ms == "bull"


def test_bear():
    ms, hs, ls = market_structure(_trend(False))
    assert ms == "bear"
