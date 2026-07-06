from core.models import Candidate, Component
from scoring.engine import ScoringEngine

CFG = {"scoring": {"min_score": 7.0, "min_rr": 2.0, "allow_long": True, "allow_short": False}}


def _cand(score_each=2.0, n=4, entry=100.0, sl=98.0, side="LONG"):
    comps = [Component(f"c{i}", score_each, "reason") for i in range(n)]
    tps = [103.0, 105.0, 108.0]
    return Candidate("BTCUSDT", side, entry, sl, tps, comps, "test")


def test_pass():
    sig, rej = ScoringEngine(CFG).score(_cand())
    assert sig is not None and rej is None
    assert sig.rr == 2.5 and sig.score == 8.0


def test_low_score():
    sig, rej = ScoringEngine(CFG).score(_cand(score_each=1.0))
    assert sig is None and "рейтинг" in rej


def test_low_rr():
    c = _cand()
    c.tps = [100.5, 101.0, 102.0]
    sig, rej = ScoringEngine(CFG).score(c)
    assert sig is None and "RR" in rej


def test_short_disabled():
    sig, rej = ScoringEngine(CFG).score(_cand(side="SHORT", sl=102.0))
    assert sig is None and "SHORT" in rej
