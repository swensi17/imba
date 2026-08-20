from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)
API = "https://api.telegram.org"


class TelegramBot:
    def __init__(self, token: str, timeout: float = 35.0) -> None:
        self.token = token
        self._offset = 0
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, **payload: Any) -> Any:
        url = f"{API}/bot{self.token}/{method}"
        r = await self._client.post(url, json=payload)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description") or f"telegram {method} failed")
        return data.get("result")

    async def get_me(self) -> dict[str, Any]:
        return await self._call("getMe")

    async def delete_webhook(self) -> None:
        await self._call("deleteWebhook", drop_pending_updates=False)

    async def get_updates(self, timeout: int = 25) -> list[dict[str, Any]]:
        result = await self._call(
            "getUpdates",
            offset=self._offset,
            timeout=timeout,
            allowed_updates=["message", "callback_query"],
        )
        updates = list(result or [])
        if updates:
            self._offset = int(updates[-1]["update_id"]) + 1
        return updates

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        parse_mode: str | None = "HTML",
        disable_web_page_preview: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return await self._call("sendMessage", **payload)
