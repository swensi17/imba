from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RepoCandidate:
    owner: str
    name: str
    full_name: str
    html_url: str
    description: str
    language: str | None
    stars: int
    forks: int
    watchers: int
    open_issues: int
    topics: list[str] = field(default_factory=list)
    license_spdx: str | None = None
    created_at: datetime | None = None
    pushed_at: datetime | None = None
    homepage: str | None = None
    default_branch: str = "main"
    source: str = "search"
    stars_today: int | None = None
    score: float = 0.0
    branch: str = "imba/latest"
    why: str = ""
    preview_url: str | None = None
    preview_path: str | None = None
    readme_excerpt: str = ""

    @property
    def slug(self) -> str:
        return f"{self.owner}__{self.name}".replace("/", "_")

    @classmethod
    def from_api(cls, raw: dict[str, Any], source: str = "search") -> "RepoCandidate":
        owner = (raw.get("owner") or {}).get("login") or raw.get("full_name", "").split("/")[0]
        name = raw.get("name") or raw.get("full_name", "").split("/")[-1]
        full = raw.get("full_name") or f"{owner}/{name}"
        topics = list(raw.get("topics") or [])
        lic = raw.get("license") or {}
        return cls(
            owner=owner,
            name=name,
            full_name=full,
            html_url=raw.get("html_url") or f"https://github.com/{full}",
            description=(raw.get("description") or "").strip(),
            language=raw.get("language"),
            stars=int(raw.get("stargazers_count") or 0),
            forks=int(raw.get("forks_count") or 0),
            watchers=int(raw.get("watchers_count") or raw.get("watchers") or 0),
            open_issues=int(raw.get("open_issues_count") or 0),
            topics=topics,
            license_spdx=(lic.get("spdx_id") if isinstance(lic, dict) else None),
            created_at=_parse_dt(raw.get("created_at")),
            pushed_at=_parse_dt(raw.get("pushed_at")),
            homepage=(raw.get("homepage") or None),
            default_branch=raw.get("default_branch") or "main",
            source=source,
        )


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
