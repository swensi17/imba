from __future__ import annotations

from datetime import datetime, timezone

from imba_radar.config.branches import BRANCHES, BranchSpec
from imba_radar.github.models import RepoCandidate

SPAM = (
    "airdrop", "free-crypto", "hack-instagram", "nude", "porn",
    "crack-license", "stealer", "rat-malware",
)


class Scorer:
    def __init__(self, min_score: float = 42.0, lang: str = "ru") -> None:
        self.min_score = min_score
        self.lang = lang

    def score(self, c: RepoCandidate) -> RepoCandidate:
        now = datetime.now(timezone.utc)
        score = 0.0
        reasons: list[str] = []

        blob = " ".join(
            [
                c.full_name.lower(),
                (c.description or "").lower(),
                " ".join(c.topics).lower(),
            ]
        )
        if any(x in blob for x in SPAM):
            c.score = 0
            c.why = "filtered"
            c.branch = "imba/latest"
            return c

        # stars base
        score += min(c.stars, 5000) ** 0.45 * 2.2
        if c.stars >= 100:
            reasons.append("известность")
        if c.stars_today and c.stars_today >= 50:
            score += min(c.stars_today, 2000) ** 0.55 * 3.5
            reasons.append(f"+{c.stars_today}★ сегодня")
        elif c.stars_today and c.stars_today >= 15:
            score += c.stars_today * 0.35
            reasons.append(f"+{c.stars_today}★ сегодня")

        # freshness
        if c.created_at:
            age_h = max(1.0, (now - c.created_at).total_seconds() / 3600)
            if age_h <= 24 * 3:
                score += 28
                reasons.append("свежий репо")
            elif age_h <= 24 * 14:
                score += 14
        if c.pushed_at:
            push_h = max(1.0, (now - c.pushed_at).total_seconds() / 3600)
            if push_h <= 36:
                score += 10
                reasons.append("активный push")

        # presentation quality
        if c.description and len(c.description) >= 24:
            score += 8
        if c.topics:
            score += min(6, len(c.topics) * 1.2)
        if c.license_spdx and c.license_spdx != "NOASSERTION":
            score += 4
        if c.homepage:
            score += 3
        if c.readme_excerpt:
            score += 6

        branch = self._route(c, blob)
        # topic bonus
        if branch.name != "imba/latest":
            score += 6

        if "trending" in c.source and (c.stars_today or 0) >= 20:
            score += 12

        c.score = round(score, 1)
        c.branch = branch.name
        c.why = self._why(c, branch, reasons)
        return c

    def accept(self, c: RepoCandidate) -> bool:
        return c.score >= self.min_score and c.why != "filtered"

    def _route(self, c: RepoCandidate, blob: str) -> BranchSpec:
        # releases hint
        if "release" in c.source:
            return _by_name("imba/releases")

        # hot by velocity
        if (c.stars_today or 0) >= 80 or ("trending" in c.source and (c.stars_today or 0) >= 40):
            return _by_name("imba/hot")

        # new
        if c.created_at:
            age_d = (datetime.now(timezone.utc) - c.created_at).total_seconds() / 86400
            if age_d <= 7 and c.stars >= 5:
                # still allow topic override below for strong matches
                new_branch = _by_name("imba/new")
            else:
                new_branch = None
        else:
            new_branch = None

        best: BranchSpec | None = None
        best_hits = 0
        for b in BRANCHES:
            if b.name in {"imba/latest", "imba/hot", "imba/new", "imba/releases"}:
                continue
            hits = sum(1 for k in b.keywords if k in blob)
            hits += sum(1 for t in c.topics if t.lower() in b.topics or t.lower() in b.keywords)
            if hits > best_hits:
                best_hits = hits
                best = b

        if best and best_hits >= 1:
            return best
        if new_branch:
            return new_branch
        if "trending" in c.source:
            return _by_name("imba/hot")
        return _by_name("imba/latest")

    def _why(self, c: RepoCandidate, branch: BranchSpec, reasons: list[str]) -> str:
        if self.lang == "ru":
            base = f"Ветка «{branch.title}»"
            if c.description:
                tip = c.description.strip()
                if len(tip) > 110:
                    tip = tip[:107] + "…"
                reasons = [tip] + reasons
            return " · ".join([base] + reasons[:3])
        return " · ".join([branch.title] + reasons[:3])


def _by_name(name: str) -> BranchSpec:
    for b in BRANCHES:
        if b.name == name:
            return b
    return BRANCHES[-1]
