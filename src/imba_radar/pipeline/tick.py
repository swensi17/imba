from __future__ import annotations

import logging
from datetime import datetime, timezone

from imba_radar.config.settings import Settings
from imba_radar.gitpub.publisher import BranchPublisher
from imba_radar.github.client import GitHubClient
from imba_radar.github.enrich import Enricher
from imba_radar.github.models import RepoCandidate
from imba_radar.github.search import SearchPoller
from imba_radar.github.trending import TrendingPoller
from imba_radar.score.scorer import Scorer
from imba_radar.store.seen import SeenStore, TickState

log = logging.getLogger(__name__)


class TickPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = GitHubClient(settings.github_token)
        self.search = SearchPoller()
        self.trending = TrendingPoller()
        self.enricher = Enricher(self.client)
        self.scorer = Scorer(min_score=settings.min_score, lang=settings.lang)
        self.seen = SeenStore(settings.data_dir / "seen.sqlite3")
        self.state = TickState(settings.data_dir / "tick.json")
        self.publisher = BranchPublisher(settings)

    async def close(self) -> None:
        await self.client.aclose()
        self.seen.close()

    async def bootstrap(self) -> None:
        self.settings.ensure_dirs()
        if not self.settings.github_token:
            raise RuntimeError("GITHUB_TOKEN is required for bootstrap")
        await self.client.ensure_repo(
            self.settings.github_owner,
            self.settings.github_repo,
            "Live GitHub imba feed - curated cards with previews",
        )
        self.publisher.ensure_local_repo()

    async def run_once(self) -> int:
        tick = self.state.bump()
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log.info("tick=%s day=%s", tick, day)

        candidates: dict[str, RepoCandidate] = {}

        # every tick: 2 search queries
        for c in await self.search.poll(self.client, queries=2):
            candidates[c.full_name] = c

        # every 5th tick: trending scrape + enrich
        if self.state.should_trending(5):
            try:
                for c in await self.trending.poll(self.client):
                    prev = candidates.get(c.full_name)
                    if prev is None or (c.stars_today or 0) > (prev.stars_today or 0):
                        candidates[c.full_name] = c
            except Exception as e:
                log.warning("trending poll failed: %s", e)

        fresh = [c for c in candidates.values() if not self.seen.has(c.full_name)]
        log.info("candidates=%s fresh=%s", len(candidates), len(fresh))

        accepted: list[RepoCandidate] = []
        for c in fresh:
            try:
                c = await self.enricher.enrich(c)
                c = self.scorer.score(c)
                if not self.scorer.accept(c):
                    continue
                accepted.append(c)
            except Exception as e:
                log.debug("skip %s: %s", c.full_name, e)

        accepted.sort(key=lambda x: x.score, reverse=True)
        accepted = accepted[: self.settings.max_cards_per_tick]
        if not accepted:
            log.info("nothing to publish")
            return 0

        self.publisher.ensure_local_repo()
        n = await self.publisher.publish(accepted, day)
        for c in accepted:
            self.seen.mark(c.full_name, c.branch, c.score)
            log.info(
                "card %s score=%.1f branch=%s",
                c.full_name,
                c.score,
                c.branch,
            )
        return n
