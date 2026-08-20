from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from imba_radar.github.client import UA
from imba_radar.github.models import RepoCandidate

log = logging.getLogger(__name__)

REPO_HREF = re.compile(
    r'href="/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)"[^>]*>\s*'
    r'(?:<span[^>]*>)?(?P=owner)\s*/\s*(?P=repo)',
    re.I,
)
STARS_TODAY = re.compile(
    r'(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+).*?'
    r'(?P<stars>[\d,]+)\s+stars?\s+today',
    re.I | re.S,
)
ARTICLE_BLOCK = re.compile(
    r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>',
    re.I | re.S,
)
OWNER_REPO = re.compile(
    r'href="/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"',
)
STARS_TODAY_IN = re.compile(r'([\d,]+)\s*</span>\s*stars?\s+today', re.I)


class TrendingPoller:
    def __init__(self) -> None:
        self._langs = ["", "python", "typescript", "go", "rust", "javascript"]
        self._idx = 0

    def next_lang(self) -> str:
        lang = self._langs[self._idx % len(self._langs)]
        self._idx += 1
        return lang

    async def poll(self, enrich_client: Any | None = None) -> list[RepoCandidate]:
        lang = self.next_lang()
        url = "https://github.com/trending"
        params = {"since": "daily"}
        if lang:
            url = f"https://github.com/trending/{lang}"
        headers = {"User-Agent": UA, "Accept": "text/html"}
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as http:
            r = await http.get(url, params=params)
            r.raise_for_status()
            html = r.text

        parsed = self._parse(html, source=f"trending:{lang or 'all'}")
        if enrich_client is None:
            return parsed

        enriched: list[RepoCandidate] = []
        for c in parsed[:12]:
            try:
                raw = await enrich_client.get_repo(c.full_name)
                full = RepoCandidate.from_api(raw, source=c.source)
                full.stars_today = c.stars_today
                enriched.append(full)
            except Exception as e:
                log.debug("enrich trending %s: %s", c.full_name, e)
                enriched.append(c)
        return enriched

    def _parse(self, html: str, source: str) -> list[RepoCandidate]:
        out: list[RepoCandidate] = []
        seen: set[str] = set()
        blocks = ARTICLE_BLOCK.findall(html)
        if not blocks:
            # fallback loose parse
            for m in OWNER_REPO.finditer(html):
                owner, repo = m.group(1), m.group(2)
                if owner in {"topics", "settings", "orgs", "users", "login"}:
                    continue
                full = f"{owner}/{repo}"
                if full in seen:
                    continue
                seen.add(full)
                out.append(
                    RepoCandidate(
                        owner=owner,
                        name=repo,
                        full_name=full,
                        html_url=f"https://github.com/{full}",
                        description="",
                        language=None,
                        stars=0,
                        forks=0,
                        watchers=0,
                        open_issues=0,
                        source=source,
                    )
                )
                if len(out) >= 15:
                    break
            return out

        for block in blocks:
            m = OWNER_REPO.search(block)
            if not m:
                continue
            owner, repo = m.group(1), m.group(2)
            full = f"{owner}/{repo}"
            if full in seen:
                continue
            seen.add(full)
            stars_today = None
            sm = STARS_TODAY_IN.search(block)
            if sm:
                stars_today = int(sm.group(1).replace(",", ""))
            desc = ""
            dm = re.search(r'<p[^>]*>(.*?)</p>', block, re.S | re.I)
            if dm:
                desc = re.sub(r"<[^>]+>", "", dm.group(1)).strip()
            out.append(
                RepoCandidate(
                    owner=owner,
                    name=repo,
                    full_name=full,
                    html_url=f"https://github.com/{full}",
                    description=desc,
                    language=None,
                    stars=0,
                    forks=0,
                    watchers=0,
                    open_issues=0,
                    source=source,
                    stars_today=stars_today,
                )
            )
        return out
