"""Демо-публикация сигнала в Telegram-канал (для скриншота в README).

Отправляет пример сигнала SOLUSDT LONG, ждёт несколько секунд, затем
переводит его в статус TP1 — редактирует исходное сообщение и шлёт
отдельное статус-уведомление, ровно как это делает SignalManager вживую.

Запуск из корня репозитория (нужен заполненный config/.env):
    python scripts/demo_signal.py
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config, load_env
from core.models import Signal
from signals.formatter import signal_text, status_text
from tg.publisher import TelegramPublisher

PAUSE_SEC = 5  # пауза перед TP1, чтобы успеть увидеть «живое» сообщение


def build_demo_signal() -> Signal:
    return Signal(
        symbol="SOLUSDT",
        side="LONG",
        entry=166.76,
        sl=165.06,
        tp1=169.31,
        tp2=171.01,
        tp3=173.56,
        rr=2.5,
        score=7.5,
        strength=8,
        reasons=[
            "Global LONG trend: price above EMA200, EMA50 > EMA100 (4H)",
            "Pullback to EMA50 zone (1H)",
            "RSI(1H) 54 — reset after pullback",
            "5M momentum in trade direction",
            "Elevated volume (15M)",
            "Funding in favor (-0.08%)",
            "Open Interest +3.2% in 4h",
        ],
        strategy="trend_pullback",
    )


def main():
    env = load_env()
    leverage = load_config().get("leverage", 10)
    pub = TelegramPublisher(env["bot_token"], env["channel_id"], env["admin_id"])

    s = build_demo_signal()
    s.message_id = pub.send(signal_text(s, leverage))
    print(f"Сигнал опубликован: message_id={s.message_id}, id={s.id}")

    time.sleep(PAUSE_SEC)

    # TP1 — как в SignalManager: стоп в безубыток, правка сообщения, статус
    s.hit.append("TP1")
    s.status = "TP1"
    s.sl_current = s.entry
    pub.edit(s.message_id, signal_text(s, leverage))
    pub.send(status_text(s, "TP1"))
    print("Статус обновлён: TP1 (сообщение отредактировано, статус отправлен)")


if __name__ == "__main__":
    main()
