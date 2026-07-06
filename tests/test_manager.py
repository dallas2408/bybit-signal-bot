import json

from core.models import Signal
from signals.manager import SignalManager


class FakePub:
    def __init__(self):
        self.sent, self.edits = [], []

    def send(self, text):
        self.sent.append(text)
        return len(self.sent)

    def edit(self, mid, text):
        self.edits.append(mid)

    def notify_admin(self, text):
        pass


CFG = {"signals": {"cooldown_minutes": 60, "max_hold_hours": 48,
                   "move_sl_to_breakeven_after_tp1": True,
                   "check_interval_sec": 60},
       "leverage": 10}


def _sig():
    return Signal(symbol="BTCUSDT", side="LONG", entry=100.0, sl=98.0,
                  tp1=103.0, tp2=105.0, tp3=108.0, rr=2.5, score=8.0,
                  strength=8, reasons=["r"], strategy="t")


def _mgr(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return SignalManager(CFG, FakePub())


def test_tp1_then_breakeven(tmp_path, monkeypatch):
    m = _mgr(tmp_path, monkeypatch)
    s = _sig()
    m.publish(s)
    assert m.is_blocked("BTCUSDT")

    m.track({"BTCUSDT": {"high": 103.5, "low": 100.5, "last": 103.2}})
    assert s.status == "TP1" and s.sl_current == 100.0  # стоп в безубытке

    m.track({"BTCUSDT": {"high": 101.0, "low": 99.5, "last": 100.0}})
    assert "BTCUSDT" not in m.active                    # закрыт по BE
    assert m.is_blocked("BTCUSDT")                      # cooldown действует
    events = [json.loads(l)["event"] for l in open("state/history.jsonl")]
    assert events == ["OPEN", "TP1", "BE"]


def test_stop_loss_first(tmp_path, monkeypatch):
    m = _mgr(tmp_path, monkeypatch)
    s = _sig()
    m.publish(s)
    # свеча зацепила и стоп, и TP1 — консервативно засчитывается стоп
    m.track({"BTCUSDT": {"high": 103.5, "low": 97.5, "last": 99.0}})
    assert s.status == "SL" and "BTCUSDT" not in m.active


def test_tp3_full_close(tmp_path, monkeypatch):
    m = _mgr(tmp_path, monkeypatch)
    s = _sig()
    m.publish(s)
    m.track({"BTCUSDT": {"high": 109.0, "low": 100.5, "last": 108.5}})
    assert s.status == "TP3"
    assert s.hit == ["TP1", "TP2", "TP3"]
    assert "BTCUSDT" not in m.active


def test_timeout_cancel(tmp_path, monkeypatch):
    m = _mgr(tmp_path, monkeypatch)
    s = _sig()
    s.created_at -= 49 * 3600  # старше max_hold_hours
    m.publish(s)
    m.track({"BTCUSDT": {"high": 100.5, "low": 99.8, "last": 100.1}})
    assert "BTCUSDT" not in m.active
    events = [json.loads(l)["event"] for l in open("state/history.jsonl")]
    assert events[-1] == "CANCELLED"
