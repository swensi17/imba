from __future__ import annotations

import logging
from typing import Awaitable, Callable

from imba_radar.config.settings import Settings
from imba_radar.telegram.client import TelegramBot

log = logging.getLogger(__name__)

ForceTick = Callable[[], Awaitable[int]]
StatusFn = Callable[[], Awaitable[str]]


class ImbaTelegramApp:
    """Owner console for imba-radar on the former hammasirr bot token."""

    def __init__(
        self,
        settings: Settings,
        *,
        force_tick: ForceTick,
        status_text: StatusFn,
    ) -> None:
        self.settings = settings
        self.force_tick = force_tick
        self.status_text = status_text
        self.bot = TelegramBot(settings.telegram_bot_token)
        self._owners = set(settings.owner_ids)
        self._username = ""

    async def start(self) -> None:
        me = await self.bot.get_me()
        self._username = str(me.get("username") or "")
        await self.bot.delete_webhook()
        log.info("telegram bot @%s ready owners=%s", self._username, sorted(self._owners))

    async def aclose(self) -> None:
        await self.bot.aclose()

    async def poll_forever(self) -> None:
        while True:
            try:
                updates = await self.bot.get_updates(timeout=25)
            except Exception:
                log.exception("telegram getUpdates failed")
                continue
            for upd in updates:
                try:
                    await self._handle_update(upd)
                except Exception:
                    log.exception("telegram update failed")

    async def notify_owners(self, text: str) -> None:
        for oid in self._owners:
            try:
                await self.bot.send_message(oid, text, disable_web_page_preview=True)
            except Exception as e:
                log.warning("notify %s: %s", oid, e)

    async def _handle_update(self, upd: dict) -> None:
        msg = upd.get("message") or {}
        if not msg:
            return
        chat = msg.get("chat") or {}
        user = msg.get("from") or {}
        chat_id = int(chat.get("id") or 0)
        user_id = int(user.get("id") or 0)
        text = str(msg.get("text") or "").strip()
        if not text or not chat_id:
            return

        # first contact becomes owner if list empty
        if not self._owners and user_id:
            self._owners.add(user_id)
            log.info("telegram owner learned: %s", user_id)

        if self._owners and user_id not in self._owners:
            await self.bot.send_message(chat_id, "⛔ Только для владельца imba-radar.")
            return

        cmd = text.split()[0].split("@")[0].lower()
        if cmd in {"/start", "/help", "/status"}:
            body = await self.status_text()
            await self.bot.send_message(chat_id, body, disable_web_page_preview=True)
            return
        if cmd in {"/tick", "/now", "/imba"}:
            await self.bot.send_message(chat_id, "⏳ Запускаю тик…")
            n = await self.force_tick()
            await self.bot.send_message(
                chat_id,
                f"✅ Тик готов. Карточек: <b>{n}</b>\n"
                f"<a href=\"https://github.com/{self.settings.repo_full_name}\">github.com/{self.settings.repo_full_name}</a>",
                disable_web_page_preview=True,
            )
            return
        if cmd == "/branches":
            await self.bot.send_message(
                chat_id,
                "\n".join(
                    [
                        "<b>Ветки</b>",
                        "• imba/hot",
                        "• imba/new",
                        "• imba/ai",
                        "• imba/bots",
                        "• imba/tools",
                        "• imba/releases",
                        "• imba/latest",
                        "",
                        f"<a href=\"https://github.com/{self.settings.repo_full_name}/branches\">открыть ветки</a>",
                    ]
                ),
                disable_web_page_preview=True,
            )
            return
        await self.bot.send_message(
            chat_id,
            "Команды: /status · /tick · /branches",
        )
