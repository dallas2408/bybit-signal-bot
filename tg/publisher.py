"""Telegram Bot API: публикация в канал, редактирование, алерты админу."""
from __future__ import annotations
import time
import logging
import requests

log = logging.getLogger("telegram")


class TelegramPublisher:
    def __init__(self, token: str, channel_id: str, admin_id: str = ""):
        self.base = f"https://api.telegram.org/bot{token}"
        self.channel_id = channel_id
        self.admin_id = admin_id

    def _call(self, method: str, payload: dict, retries: int = 3) -> dict:
        last = None
        for i in range(retries):
            try:
                r = requests.post(f"{self.base}/{method}", json=payload, timeout=15)
                data = r.json()
                if data.get("ok"):
                    return data["result"]
                # rate limit
                retry_after = data.get("parameters", {}).get("retry_after")
                if retry_after:
                    time.sleep(retry_after + 1)
                    continue
                last = RuntimeError(f"{method}: {data.get('description')}")
            except Exception as e:
                last = e
            time.sleep(2 * (i + 1))
        raise RuntimeError(f"Telegram API fail: {last}")

    def send(self, text: str) -> int:
        res = self._call("sendMessage", {
            "chat_id": self.channel_id, "text": text,
            "parse_mode": "HTML", "disable_web_page_preview": True})
        return res["message_id"]

    def edit(self, message_id: int, text: str):
        try:
            self._call("editMessageText", {
                "chat_id": self.channel_id, "message_id": message_id,
                "text": text, "parse_mode": "HTML",
                "disable_web_page_preview": True})
        except RuntimeError as e:
            if "message is not modified" not in str(e):
                raise

    def notify_admin(self, text: str):
        if not self.admin_id:
            return
        try:
            self._call("sendMessage", {"chat_id": self.admin_id, "text": f"⚠️ {text}"})
        except Exception as e:
            log.error("Admin notify fail: %s", e)
