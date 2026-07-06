"""Форматирование сообщений Telegram (HTML)."""
from __future__ import annotations
import time
from core.models import Signal

STATUS_LABEL = {
    "ACTIVE": "🟢 Активен",
    "TP1": "✅ TP1 достигнут",
    "TP2": "✅✅ TP2 достигнут",
    "TP3": "🏆 TP3 достигнут — сделка закрыта",
    "SL": "🛑 Stop Loss",
    "BE": "⚪ Закрыт в безубытке (стоп после TP1)",
    "CANCELLED": "⚪ Отменён (условия перестали выполняться)",
}


def _fmt(x: float) -> str:
    if x >= 100: return f"{x:,.2f}"
    if x >= 1:   return f"{x:.4f}"
    return f"{x:.6f}"


def signal_text(s: Signal, leverage: int) -> str:
    emoji = "🟩 LONG" if s.side == "LONG" else "🟥 SHORT"
    ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(s.created_at))
    reasons = "\n".join(f"  • {r}" for r in s.reasons)
    return (
        f"<b>{emoji} — {s.symbol}</b>\n\n"
        f"Вход: <code>{_fmt(s.entry)}</code>\n"
        f"Stop Loss: <code>{_fmt(s.sl)}</code>\n"
        f"TP1: <code>{_fmt(s.tp1)}</code>\n"
        f"TP2: <code>{_fmt(s.tp2)}</code>\n"
        f"TP3: <code>{_fmt(s.tp3)}</code>\n\n"
        f"Risk/Reward (TP2): <b>1:{s.rr}</b>\n"
        f"Сила сигнала: <b>{s.strength}/10</b>\n"
        f"Плечо (расчётное): {leverage}x\n\n"
        f"<b>Причины:</b>\n{reasons}\n\n"
        f"Статус: {STATUS_LABEL[s.status]}\n"
        f"⏱ {ts} | id {s.id}"
    )


def status_text(s: Signal, event: str) -> str:
    return f"<b>{s.symbol} {s.side}</b> (id {s.id}): {STATUS_LABEL[event]}"
