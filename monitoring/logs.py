"""Логирование: консоль + ротация файлов + jsonl-журналы сигналов/отказов."""
from __future__ import annotations
import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler


def setup_logging(cfg: dict):
    d = cfg["logging"]["dir"]
    os.makedirs(d, exist_ok=True)
    level = getattr(logging, cfg["logging"].get("level", "INFO"))
    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    root = logging.getLogger()
    root.setLevel(level)
    ch = logging.StreamHandler(); ch.setFormatter(fmt)
    fh = RotatingFileHandler(os.path.join(d, "bot.log"),
                             maxBytes=10_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    root.handlers = [ch, fh]


def log_rejection(symbol: str, stage: str, reason: str, logdir: str = "logs"):
    with open(os.path.join(logdir, "rejections.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "symbol": symbol,
                            "stage": stage, "reason": reason}, ensure_ascii=False) + "\n")


class AlertThrottle:
    """Не заваливать админа одинаковыми алертами."""
    def __init__(self, minutes: int = 10):
        self.window = minutes * 60
        self.last: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        if now - self.last.get(key, 0) > self.window:
            self.last[key] = now
            return True
        return False
