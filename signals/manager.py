"""Сопровождение сигналов: Активен/TP1/TP2/TP3/SL/BE/Отменён,
безубыток после TP1, cooldown по монете, персистентность в JSON.

v1.1: триггеры считаются по high/low минутных свечей с последней проверки
(а не по одному lastPrice) — проколы фитилём больше не пропускаются,
логика совпадает с бэктестом (стоп проверяется первым, консервативно).
"""
from __future__ import annotations
import json
import os
import time
import logging

from core.models import Signal
from signals.formatter import signal_text, status_text

log = logging.getLogger("signals")

STATE_FILE = "state/active_signals.json"
HISTORY_FILE = "state/history.jsonl"


class SignalManager:
    def __init__(self, cfg: dict, publisher):
        self.cfg = cfg["signals"]
        self.leverage = cfg.get("leverage", 10)
        self.publisher = publisher
        self.active: dict[str, Signal] = {}      # symbol -> Signal
        self.cooldown_until: dict[str, float] = {}
        os.makedirs("state", exist_ok=True)
        self._load()

    # ---------- персистентность ----------
    def _load(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.active = {k: Signal.from_dict(v) for k, v in data.get("active", {}).items()}
                self.cooldown_until = data.get("cooldown", {})
                log.info("Восстановлено активных сигналов: %d", len(self.active))
            except Exception as e:
                log.error("Не удалось загрузить состояние: %s", e)

    def _save(self):
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"active": {k: s.to_dict() for k, s in self.active.items()},
                       "cooldown": self.cooldown_until}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE_FILE)

    def _history(self, s: Signal, event: str, px: float | None = None):
        row = {"event": event, "ts": time.time(), **s.to_dict()}
        if px is not None:
            row["close_px"] = px
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ---------- API ----------
    def is_blocked(self, symbol: str) -> bool:
        """Активная сделка или cooldown => повторный сигнал не отправляем."""
        if symbol in self.active:
            return True
        return time.time() < self.cooldown_until.get(symbol, 0)

    def publish(self, s: Signal):
        try:
            s.message_id = self.publisher.send(signal_text(s, self.leverage))
        except Exception as e:
            log.error("Telegram send fail %s: %s", s.symbol, e)
            try:
                self.publisher.notify_admin(f"Не удалось опубликовать сигнал {s.symbol}: {e}")
            except Exception:
                pass
        self.active[s.symbol] = s
        self._history(s, "OPEN")
        self._save()
        log.info("СИГНАЛ %s %s score=%.1f rr=%.2f", s.side, s.symbol, s.score, s.rr)

    def track(self, marks: dict[str, dict]):
        """Один тик сопровождения.
        marks: symbol -> {"high": max за окно, "low": min за окно, "last": цена}.
        Порядок как в бэктесте: сначала стоп (консервативно), затем тейки по порядку.
        Остаточный краевой случай: сразу после переноса стопа в безубыток
        в окно могут попасть свечи до TP1 с low < entry — окно ограничено
        elapsed в main.track(), эффект минимален."""
        now = time.time()
        for symbol in list(self.active):
            s = self.active[symbol]
            m = marks.get(symbol)
            if not m:
                continue
            sgn = 1 if s.side == "LONG" else -1
            adverse = m["low"] if sgn > 0 else m["high"]
            favor = m["high"] if sgn > 0 else m["low"]

            # 1) стоп — первым
            if sgn * (adverse - s.sl_current) <= 0:
                if s.hit:   # стоп уже в безубытке
                    self._close(s, s.status, note_event="BE", px=s.sl_current)
                else:
                    self._close(s, "SL", note_event="SL", px=s.sl_current)
                continue

            # 2) тейки строго по порядку
            closed = False
            for lvl, tp in (("TP1", s.tp1), ("TP2", s.tp2), ("TP3", s.tp3)):
                if lvl in s.hit:
                    continue
                if sgn * (favor - tp) < 0:
                    break
                s.hit.append(lvl)
                s.status = lvl
                if lvl == "TP1" and self.cfg.get("move_sl_to_breakeven_after_tp1", True):
                    s.sl_current = s.entry
                if lvl == "TP3":
                    self._close(s, "TP3", note_event="TP3", px=s.tp3)
                    closed = True
                    break
                self._update(s, lvl)
            if closed:
                continue

            # 3) таймаут — для любого незакрытого сигнала (в т.ч. застрявшего на TP1/TP2)
            if now - s.created_at > self.cfg["max_hold_hours"] * 3600:
                final = s.status if s.hit else "CANCELLED"
                self._close(s, final, note_event="CANCELLED", px=m.get("last"))

    # ---------- внутреннее ----------
    def _update(self, s: Signal, event: str):
        self._history(s, event)
        self._save()
        try:
            if s.message_id:
                self.publisher.edit(s.message_id, signal_text(s, self.leverage))
            self.publisher.send(status_text(s, event))
        except Exception as e:
            log.error("Telegram update fail %s: %s", s.symbol, e)
        log.info("%s %s -> %s", s.symbol, s.side, event)

    def _close(self, s: Signal, final_status: str, note_event: str, px: float | None = None):
        s.status = final_status
        s.closed_at = time.time()
        self._history(s, note_event, px=px)
        try:
            if s.message_id:
                self.publisher.edit(s.message_id, signal_text(s, self.leverage))
            self.publisher.send(status_text(s, note_event))
        except Exception as e:
            log.error("Telegram close fail %s: %s", s.symbol, e)
        del self.active[s.symbol]
        self.cooldown_until[s.symbol] = time.time() + self.cfg["cooldown_minutes"] * 60
        self._save()
        log.info("%s %s закрыт: %s", s.symbol, s.side, note_event)
