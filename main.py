"""Точка входа: цикл 24/7 — вселенная -> сканирование -> скоринг ->
публикация -> сопровождение. Запуск: python main.py
"""
from __future__ import annotations
import logging
import time

from core.config import load_config, load_env
from core.registry import build_strategies
from data.bybit_client import BybitClient, BybitError
from data.market_data import MarketData
from filters.liquidity import build_universe, ticker_metrics
from analysis import regime as regime_mod
from scoring.engine import ScoringEngine
from signals.manager import SignalManager
from tg.publisher import TelegramPublisher
from monitoring.logs import setup_logging, log_rejection, AlertThrottle

log = logging.getLogger("main")


class Bot:
    def __init__(self):
        self.cfg = load_config()
        env = load_env()
        setup_logging(self.cfg)

        self.client = BybitClient()
        self.mdata = MarketData(self.client, self.cfg)
        self.strategies = build_strategies(self.cfg)
        self.scoring = ScoringEngine(self.cfg)
        self.publisher = TelegramPublisher(env["bot_token"], env["channel_id"], env["admin_id"])
        self.manager = SignalManager(self.cfg, self.publisher)
        self.throttle = AlertThrottle(self.cfg["alerts"]["throttle_minutes"])

        self.universe: list[str] = []
        self._last_universe = 0.0
        self._last_scan = 0.0
        self._last_track = 0.0
        self._last_heartbeat = 0.0
        self.stats = {"scans": 0, "signals": 0, "rejections": 0, "errors": 0}

    # ---------- шаги ----------
    def refresh_universe(self):
        tickers = self.client.tickers()
        self.universe = build_universe(tickers, self.cfg)

    def scan(self):
        tickers = {t["symbol"]: t for t in self.client.tickers()}
        for symbol in self.universe:
            if self.manager.is_blocked(symbol):
                continue
            try:
                self._scan_symbol(symbol, tickers.get(symbol))
            except (BybitError, ValueError) as e:
                log.warning("scan %s: %s", symbol, e)
                self.stats["errors"] += 1
            time.sleep(self.cfg["scan"]["pause_between_symbols_sec"])
        self.stats["scans"] += 1

    def _scan_symbol(self, symbol: str, ticker: dict | None):
        if ticker is None:
            return
        m = ticker_metrics(ticker)
        # спред проверяем в момент сигнала, а не только при отборе вселенной
        if m["spread_pct"] > self.cfg["universe"]["max_spread_pct"]:
            log_rejection(symbol, "spread", f"спред {m['spread_pct']:.3f}% выше лимита")
            self.stats["rejections"] += 1
            return
        snap = self.mdata.snapshot(symbol)

        # фильтр рынка: во флэте по 1H сигналов нет
        reg = regime_mod.detect(snap["main"], self.cfg["regime"])
        if reg["regime"] == "flat":
            log_rejection(symbol, "regime", "флэт (1H) — без подтверждений не работаем")
            self.stats["rejections"] += 1
            return

        ctx = {
            "symbol": symbol,
            "last_price": m["last_price"],
            "funding": m["funding"],
            "spread_pct": m["spread_pct"],
            "oi_change_pct": self.client.oi_change_pct(symbol),
            "regime": reg,
        }

        for strat in self.strategies:
            cand, reject = strat.evaluate(snap, ctx)
            if cand is None:
                log_rejection(symbol, strat.name, reject or "нет кандидата")
                self.stats["rejections"] += 1
                continue
            sig, reject = self.scoring.score(cand)
            if sig is None:
                log_rejection(symbol, "scoring", reject or "порог")
                self.stats["rejections"] += 1
                continue
            self.manager.publish(sig)
            self.stats["signals"] += 1
            break  # один сигнал на монету за проход, даже при нескольких стратегиях

    def track(self, elapsed: float):
        """Триггеры по high/low минутных свечей за прошедшее окно —
        проколы фитилём между проверками не теряются."""
        if not self.manager.active:
            return
        limit = min(30, max(3, int(elapsed // 60) + 2))
        marks = {}
        for sym in list(self.manager.active):
            try:
                df = self.client.klines(sym, "1", limit=limit, drop_forming=False)
                marks[sym] = {"high": float(df["high"].max()),
                              "low": float(df["low"].min()),
                              "last": float(df["close"].iloc[-1])}
            except Exception as e:
                log.warning("track %s: %s", sym, e)
        if marks:
            self.manager.track(marks)

    def heartbeat(self):
        log.info("HEARTBEAT universe=%d active=%d stats=%s",
                 len(self.universe), len(self.manager.active), self.stats)

    # ---------- цикл ----------
    def run(self):
        log.info("Старт. Стратегии: %s", [s.name for s in self.strategies])
        self.publisher.notify_admin("Бот запущен")
        while True:
            now = time.time()
            try:
                if now - self._last_universe > self.cfg["universe"]["refresh_minutes"] * 60:
                    self.refresh_universe()
                    self._last_universe = now
                if now - self._last_track > self.cfg["signals"]["check_interval_sec"]:
                    self.track(now - self._last_track if self._last_track else 120.0)
                    self._last_track = now
                if now - self._last_scan > self.cfg["scan"]["interval_sec"]:
                    self.scan()
                    self._last_scan = now
                if now - self._last_heartbeat > 3600:
                    self.heartbeat()
                    self._last_heartbeat = now

                if self.client.consecutive_failures >= self.cfg["alerts"]["bybit_fail_threshold"]:
                    if self.throttle.allow("bybit_down"):
                        self.publisher.notify_admin("Потеря соединения с Bybit API")
            except BybitError as e:
                log.error("Bybit: %s", e)
                if self.throttle.allow("bybit_error"):
                    self.publisher.notify_admin(f"Ошибка Bybit API: {e}")
            except Exception as e:
                log.exception("Loop error")
                self.stats["errors"] += 1
                if self.throttle.allow("loop_error"):
                    self.publisher.notify_admin(f"Ошибка в цикле: {e}")
            time.sleep(5)


if __name__ == "__main__":
    try:
        Bot().run()
    except KeyboardInterrupt:
        print("Остановлено вручную")
