from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time

from imba_radar.config.settings import load_settings
from imba_radar.pipeline.tick import TickPipeline
from imba_radar.telegram.bot import ImbaTelegramApp


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # httpx logs full URLs; Telegram token must never appear in PM2 logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


async def _amain(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="imba-radar")
    parser.add_argument("command", choices=["run", "once", "bootstrap"])
    args = parser.parse_args(argv)

    settings = load_settings()
    _setup_logging(settings.log_level)
    settings.ensure_dirs()

    pipe = TickPipeline(settings)
    tg: ImbaTelegramApp | None = None
    stats = {"ticks": 0, "cards": 0, "last_n": 0, "last_at": 0.0, "started": time.time()}

    async def force_tick() -> int:
        n = await pipe.run_once()
        stats["ticks"] += 1
        stats["cards"] += n
        stats["last_n"] = n
        stats["last_at"] = time.time()
        return n

    async def status_text() -> str:
        up = int(time.time() - stats["started"])
        last = "-"
        if stats["last_at"]:
            last = f"{int(time.time() - stats['last_at'])}s ago · {stats['last_n']} cards"
        return "\n".join(
            [
                "<b>imba-radar</b> · online",
                f"Репо: <a href=\"https://github.com/{settings.repo_full_name}\">{settings.repo_full_name}</a>",
                f"Интервал: <code>{settings.poll_interval_sec}s</code>",
                f"Тиков: <code>{stats['ticks']}</code> · карточек: <code>{stats['cards']}</code>",
                f"Последний тик: {last}",
                f"Uptime: <code>{up}s</code>",
                "",
                "Команды: /status · /tick · /branches",
            ]
        )

    try:
        if args.command == "bootstrap":
            await pipe.bootstrap()
            logging.info("bootstrap ok -> %s", settings.repo_full_name)
            return 0
        if args.command == "once":
            n = await pipe.run_once()
            logging.info("published=%s", n)
            return 0

        if not settings.github_token:
            logging.error("GITHUB_TOKEN missing")
            return 2
        await pipe.bootstrap()

        tasks: list[asyncio.Task] = []
        if settings.telegram_bot_token:
            tg = ImbaTelegramApp(settings, force_tick=force_tick, status_text=status_text)
            await tg.start()
            tasks.append(asyncio.create_task(tg.poll_forever(), name="telegram"))
            await tg.notify_owners(
                "✅ <b>imba-radar</b> запущен на этом боте.\n"
                f"GitHub: https://github.com/{settings.repo_full_name}\n"
                "Старый Private World удалён."
            )
        else:
            logging.warning("TELEGRAM_BOT_TOKEN empty - GitHub-only mode")

        async def ticker() -> None:
            while True:
                try:
                    n = await force_tick()
                    logging.info("tick published=%s", n)
                    if tg and n > 0:
                        await tg.notify_owners(
                            f"🔥 Новый тик: <b>{n}</b> карточек → "
                            f"<a href=\"https://github.com/{settings.repo_full_name}\">{settings.repo_full_name}</a>"
                        )
                except Exception:
                    logging.exception("tick failed")
                await asyncio.sleep(settings.poll_interval_sec)

        tasks.append(asyncio.create_task(ticker(), name="ticker"))
        await asyncio.gather(*tasks)
        return 0
    finally:
        if tg:
            await tg.aclose()
        await pipe.close()


def main() -> None:
    raise SystemExit(asyncio.run(_amain(sys.argv[1:])))


if __name__ == "__main__":
    main()
