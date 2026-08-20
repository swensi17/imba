from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx

from imba_radar.github.client import UA
from imba_radar.github.models import RepoCandidate

log = logging.getLogger(__name__)

MAX_BYTES = 1_800_000


class PreviewFetcher:
    async def fetch_to(self, candidate: RepoCandidate, dest: Path) -> Path | None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        urls: list[str] = []
        if candidate.preview_url:
            urls.append(candidate.preview_url)
        # always keep OG as reliable visual
        og = f"https://opengraph.githubassets.com/{candidate.slug}/{candidate.owner}/{candidate.name}"
        if og not in urls:
            urls.append(og)

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": UA},
        ) as http:
            for url in urls:
                try:
                    r = await http.get(url)
                    if r.status_code >= 400:
                        continue
                    data = r.content
                    if not data or len(data) < 800 or len(data) > MAX_BYTES:
                        continue
                    ctype = (r.headers.get("content-type") or "").lower()
                    ext = _ext(ctype, url)
                    if ext == ".svg":
                        continue
                    path = dest.with_suffix(ext)
                    path.write_bytes(data)
                    candidate.preview_path = path.name
                    return path
                except Exception as e:
                    log.debug("preview fail %s: %s", url, e)
        return None


def _ext(ctype: str, url: str) -> str:
    if "png" in ctype:
        return ".png"
    if "jpeg" in ctype or "jpg" in ctype:
        return ".jpg"
    if "webp" in ctype:
        return ".webp"
    if "gif" in ctype:
        return ".gif"
    m = re.search(r"\.(png|jpe?g|webp|gif)(?:\?|$)", url, re.I)
    if m:
        e = m.group(1).lower()
        return ".jpg" if e == "jpeg" else f".{e}"
    return ".jpg"
