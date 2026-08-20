from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

API = "https://api.github.com"
UA = "imba-radar/1.0 (+https://github.com/swensi17/imba)"


class GitHubClient:
    def __init__(self, token: str = "", timeout: float = 25.0) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": UA,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._token = token
        self._client = httpx.AsyncClient(
            base_url=API,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        r = await self._client.get(path, params=params)
        remaining = r.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) < 20:
            log.warning("github rate remaining=%s", remaining)
        if r.status_code == 403 and "rate limit" in r.text.lower():
            raise RuntimeError("GitHub API rate limit")
        r.raise_for_status()
        return r.json()

    async def search_repositories(self, query: str, per_page: int = 20) -> list[dict[str, Any]]:
        data = await self.get(
            "/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": per_page},
        )
        return list(data.get("items") or [])

    async def get_repo(self, full_name: str) -> dict[str, Any]:
        return await self.get(f"/repos/{full_name}")

    async def get_readme_text(self, full_name: str) -> str:
        try:
            r = await self._client.get(
                f"/repos/{full_name}/readme",
                headers={"Accept": "application/vnd.github.raw"},
            )
            if r.status_code >= 400:
                return ""
            return r.text[:8000]
        except Exception as e:
            log.debug("readme fail %s: %s", full_name, e)
            return ""

    async def ensure_repo(self, owner: str, name: str, description: str) -> dict[str, Any]:
        try:
            return await self.get(f"/repos/{owner}/{name}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise
        payload = {
            "name": name,
            "description": description,
            "private": False,
            "auto_init": True,
            "has_issues": False,
            "has_projects": False,
            "has_wiki": False,
        }
        r = await self._client.post("/user/repos", json=payload)
        if r.status_code == 404:
            # org?
            r = await self._client.post(f"/orgs/{owner}/repos", json=payload)
        r.raise_for_status()
        return r.json()

    async def raw_get_bytes(self, url: str) -> bytes | None:
        try:
            r = await self._client.get(url)
            if r.status_code >= 400:
                return None
            ctype = (r.headers.get("content-type") or "").lower()
            if "html" in ctype and "image" not in ctype:
                return None
            return r.content
        except Exception:
            return None
