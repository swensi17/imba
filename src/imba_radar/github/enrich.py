from __future__ import annotations

import logging
import re

from imba_radar.github.client import GitHubClient
from imba_radar.github.models import RepoCandidate

log = logging.getLogger(__name__)

IMG_MD = re.compile(
    r"!\[[^\]]*\]\((https?://[^)\s]+)\)",
    re.I,
)
IMG_HTML = re.compile(
    r'<img[^>]+src=["\'](https?://[^"\']+)["\']',
    re.I,
)
BAD_IMG = re.compile(
    r"(badge|shields\.io|camo\.githubusercontent\.com/.*/badge|img\.shields|"
    r"travis-ci|circleci|codecov|buymeacoffee|liberapay|stars\.svg)",
    re.I,
)


class Enricher:
    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    async def enrich(self, candidate: RepoCandidate) -> RepoCandidate:
        if candidate.stars <= 0 or not candidate.language:
            try:
                raw = await self._client.get_repo(candidate.full_name)
                full = RepoCandidate.from_api(raw, source=candidate.source)
                full.stars_today = candidate.stars_today
                candidate = full
            except Exception as e:
                log.debug("repo enrich %s: %s", candidate.full_name, e)

        readme = await self._client.get_readme_text(candidate.full_name)
        candidate.readme_excerpt = _excerpt(readme)
        candidate.preview_url = _pick_readme_image(readme) or _opengraph_url(candidate)
        return candidate


def _excerpt(readme: str) -> str:
    if not readme:
        return ""
    lines = []
    for line in readme.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("!") or s.startswith("[!"):
            continue
        if s.startswith("```"):
            break
        lines.append(s)
        if len(" ".join(lines)) > 280:
            break
    text = " ".join(lines)
    return text[:320].rstrip() + ("…" if len(text) > 320 else "")


def _pick_readme_image(readme: str) -> str | None:
    for rx in (IMG_MD, IMG_HTML):
        for m in rx.finditer(readme or ""):
            url = m.group(1).strip()
            if BAD_IMG.search(url):
                continue
            if any(url.lower().endswith(ext) for ext in (".svg",)):
                continue
            return url
    return None


def _opengraph_url(c: RepoCandidate) -> str:
    # GitHub auto social card; cache-bust with pushed/created stamp
    stamp = "1"
    if c.pushed_at:
        stamp = str(int(c.pushed_at.timestamp()))
    return f"https://opengraph.githubassets.com/{stamp}/{c.owner}/{c.name}"
