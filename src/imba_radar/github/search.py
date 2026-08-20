from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from imba_radar.github.client import GitHubClient
from imba_radar.github.models import RepoCandidate

log = logging.getLogger(__name__)


class SearchPoller:
    """Rotating GitHub Search queries - keeps under Search API budget."""

    def __init__(self) -> None:
        self._cursor = 0
        self._queries = self._build_queries()

    @staticmethod
    def _build_queries() -> list[tuple[str, str]]:
        today = datetime.now(timezone.utc).date().isoformat()
        week = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        day = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        return [
            (f"created:>{today} stars:>5", "new"),
            (f"created:>{week} stars:>80", "hot"),
            (f"pushed:>{day} stars:>200 topic:ai", "ai"),
            (f"pushed:>{day} stars:>50 topic:llm", "ai"),
            (f"pushed:>{day} stars:>30 topic:telegram-bot", "bots"),
            (f"pushed:>{day} stars:>40 topic:cli", "tools"),
            (f"pushed:>{day} stars:>100 topic:mcp", "ai"),
            (f"created:>{week} stars:>40 language:TypeScript", "hot"),
            (f"created:>{week} stars:>40 language:Python", "hot"),
            (f"pushed:>{day} stars:>80 topic:discord-bot", "bots"),
        ]

    def next_batch(self, n: int = 2) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        total = len(self._queries)
        for _ in range(min(n, total)):
            out.append(self._queries[self._cursor % total])
            self._cursor += 1
        return out

    async def poll(self, client: GitHubClient, queries: int = 2) -> list[RepoCandidate]:
        found: dict[str, RepoCandidate] = {}
        for query, source in self.next_batch(queries):
            try:
                items = await client.search_repositories(query, per_page=15)
            except Exception as e:
                log.warning("search fail q=%r: %s", query, e)
                continue
            for raw in items:
                if raw.get("fork") or raw.get("archived"):
                    continue
                c = RepoCandidate.from_api(raw, source=f"search:{source}")
                prev = found.get(c.full_name)
                if prev is None or c.stars > prev.stars:
                    found[c.full_name] = c
        return list(found.values())
