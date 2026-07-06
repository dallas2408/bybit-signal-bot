"""Стратегия: откат к EMA50 (1H) по глобальному тренду 4H,
подтверждение структурой 15M и импульсом 5M.

Факторы (веса настраиваются здесь, порог — в scoring.min_score):
  +2.0  тренд 4H (цена vs EMA200, EMA50 vs EMA100)
  +1.5  цена в зоне отката к EMA50 (1H)
  +1.0  RSI 1H в зоне перезагрузки
  +1.0  MACD-гистограмма 1H разворачивается в сторону сделки
  +1.5  структура 15M совпадает (HH/HL или LH/LL)
  +1.0  свеча-подтверждение 15M
  +1.0  импульс 5M в сторону сделки
  +1.0  всплеск объёма 15M
  +0.5  фандинг в пользу / -1.0 фандинг против (перегрев)
  +0.5  рост Open Interest

Вето (кандидат не создаётся):
  - нет глобального тренда 4H;
  - цена растянута от EMA50 дальше max_extension_atr (движение уже произошло);
  - структура 15M против направления.
"""
from __future__ import annotations

from core.models import Candidate, Component
from core.registry import register_strategy
from strategies.base import BaseStrategy
from analysis.structure import market_structure


@register_strategy("trend_pullback")
class TrendPullback(BaseStrategy):

    def evaluate(self, snap: dict, ctx: dict):
        p = self.params
        d4, d1, d15 = snap["trend"], snap["main"], snap["entry"]
        d5 = snap.get("confirm")
        t4, t1, t15 = d4.iloc[-1], d1.iloc[-1], d15.iloc[-1]
        comps: list[Component] = []

        # --- 1. Глобальный тренд 4H ---
        if t4["close"] > t4["ema_slow"] and t4["ema_fast"] > t4["ema_mid"]:
            side, sgn = "LONG", 1
        elif t4["close"] < t4["ema_slow"] and t4["ema_fast"] < t4["ema_mid"]:
            side, sgn = "SHORT", -1
        else:
            return None, "нет выраженного глобального тренда (4H)"
        comps.append(Component(
            "trend_4h", 2.0,
            f"Глобальный тренд {side}: цена {'выше' if sgn > 0 else 'ниже'} EMA200, "
            f"EMA50 {'>' if sgn > 0 else '<'} EMA100 (4H)"))

        atr1 = float(t1["atr"]) or 1e-12

        # --- 2. Анти-догонялка: движение уже произошло ---
        ext = sgn * (float(t1["close"]) - float(t1["ema_fast"])) / atr1
        if ext > p["max_extension_atr"]:
            return None, f"движение уже произошло: растяжение {ext:.1f} ATR от EMA50 (1H)"

        # --- 3. Откат к зоне EMA50 (1H) ---
        if abs(float(t1["close"]) - float(t1["ema_fast"])) <= p["pullback_zone_atr"] * atr1:
            comps.append(Component("pullback_1h", 1.5, "Откат к зоне EMA50 (1H)"))

        # --- 4. RSI 1H в зоне перезагрузки ---
        lo, hi = ((p["rsi_long_min"], p["rsi_long_max"]) if sgn > 0
                  else (p["rsi_short_min"], p["rsi_short_max"]))
        if lo <= float(t1["rsi"]) <= hi:
            comps.append(Component("rsi_1h", 1.0, f"RSI(1H) {t1['rsi']:.0f} — перезагрузка после отката"))

        # --- 5. MACD 1H разворачивается в сторону сделки ---
        h = d1["macd_hist"].iloc[-3:].values
        if len(h) == 3 and sgn * (h[-1] - h[-2]) > 0 and sgn * (h[-2] - h[-3]) >= 0:
            comps.append(Component("macd_1h", 1.0, "MACD-гистограмма (1H) разворачивается в сторону сделки"))

        # --- 6. Структура 15M ---
        ms, hs, ls = market_structure(d15.tail(120).reset_index(drop=True), p["swing_window"])
        want = "bull" if sgn > 0 else "bear"
        against = "bear" if sgn > 0 else "bull"
        if ms == against:
            return None, f"структура 15M против направления ({ms})"
        if ms == want:
            label = "HH/HL" if sgn > 0 else "LH/LL"
            comps.append(Component("structure_15m", 1.5, f"Структура 15M подтверждает: {label}"))

        # --- 7. Свеча-подтверждение 15M ---
        prev15 = d15.iloc[-2]
        if sgn * (float(t15["close"]) - float(t15["open"])) > 0 and (
                (sgn > 0 and t15["close"] > prev15["high"]) or
                (sgn < 0 and t15["close"] < prev15["low"])):
            comps.append(Component("candle_15m", 1.0, "Импульсная свеча-подтверждение (15M)"))

        # --- 8. Подтверждение 5M ---
        if d5 is not None and len(d5) > 2:
            t5 = d5.iloc[-1]
            if sgn * (float(t5["close"]) - float(t5["open"])) > 0 and \
               sgn * (float(t5["close"]) - float(t5["ema_fast"])) > 0:
                comps.append(Component("confirm_5m", 1.0, "Импульс 5M в сторону сделки"))

        # --- 9. Объём 15M ---
        if t15["vol_sma"] > 0 and float(t15["volume"]) > p["volume_spike_mult"] * float(t15["vol_sma"]):
            comps.append(Component("volume_15m", 1.0, "Повышенный объём (15M)"))

        # --- 10. Funding rate ---
        f = ctx.get("funding")
        if f is not None:
            if sgn * f > p["funding_extreme"]:
                comps.append(Component("funding", -1.0, f"Фандинг против ({f:+.4%}) — перегрев толпы"))
            elif sgn * f < -p["funding_extreme"]:
                comps.append(Component("funding", 0.5, f"Фандинг в пользу сделки ({f:+.4%})"))

        # --- 11. Open Interest ---
        oi = ctx.get("oi_change_pct")
        if oi is not None and oi > 1.0:
            comps.append(Component("oi", 0.5, f"Рост Open Interest +{oi:.1f}% за 4ч"))

        # --- Уровни ---
        entry = float(ctx.get("last_price") or t15["close"])
        atr15 = float(t15["atr"]) or 1e-12

        if sgn > 0:
            swing = ls[-1][1] if ls else None
            sl = (swing - p["sl_atr_pad"] * atr15) if swing else entry - p["fallback_sl_atr"] * atr15
            if entry - sl > p["max_sl_atr"] * atr15 or sl >= entry:
                sl = entry - p["fallback_sl_atr"] * atr15
        else:
            swing = hs[-1][1] if hs else None
            sl = (swing + p["sl_atr_pad"] * atr15) if swing else entry + p["fallback_sl_atr"] * atr15
            if sl - entry > p["max_sl_atr"] * atr15 or sl <= entry:
                sl = entry + p["fallback_sl_atr"] * atr15

        risk = abs(entry - sl)
        tps = [entry + sgn * r * risk for r in p["tp_r"]]

        # веса применяются на уровне стратегии
        for c in comps:
            c.score *= self.weight

        return Candidate(symbol=ctx["symbol"], side=side, entry=entry, sl=sl,
                         tps=tps, components=comps, strategy=self.name), None
