"""Загрузка конфигурации и переменных окружения."""
import os
import yaml
from dotenv import load_dotenv

REQUIRED_ENV = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID"]


def load_config(path: str = "config/config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_env(path: str = "config/.env") -> dict:
    load_dotenv(path)
    env = {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "channel_id": os.getenv("TELEGRAM_CHANNEL_ID", ""),
        "admin_id": os.getenv("TELEGRAM_ADMIN_ID", ""),
    }
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Не заданы переменные окружения: {missing} (см. config/.env.example)")
    return env
