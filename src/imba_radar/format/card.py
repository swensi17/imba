from __future__ import annotations

from datetime import datetime, timezone

from imba_radar.config.branches import get_branch
from imba_radar.github.models import RepoCandidate


def render_card(c: RepoCandidate, day: str | None = None) -> str:
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    branch = get_branch(c.branch)
    branch_title = branch.title if branch else "Latest"
    stars = _fmt_int(c.stars)
    forks = _fmt_int(c.forks)
    lang = c.language or "n/a"
    lic = c.license_spdx or "n/a"
    topics = ", ".join(f"`{t}`" for t in c.topics[:8]) or "_нет_"
    preview = ""
    if c.preview_path:
        preview = f"![preview](../assets/{c.preview_path})\n\n"
    elif c.preview_url:
        preview = f"![preview]({c.preview_url})\n\n"

    velocity = ""
    if c.stars_today:
        velocity = f" · **📈 +{_fmt_int(c.stars_today)} / сегодня**"

    desc = (c.description or "Без описания").strip()
    why = c.why or branch_title
    excerpt = c.readme_excerpt.strip()
    homepage = f" · [сайт]({c.homepage})" if c.homepage else ""

    return f"""# {c.full_name}

{preview}**⭐ {stars}**{velocity} · **язык: {lang}** · **forks: {forks}** · **license: {lic}**

> {why}

## Суть

{desc}

## Почему в ленте

- ветка: `{c.branch}` ({branch_title})
- score: `{c.score}`
- источник: `{c.source}`
- топики: {topics}

{f"## Из README{chr(10)}{chr(10)}{excerpt}{chr(10)}" if excerpt else ""}
## Ссылки

[Репозиторий]({c.html_url}){homepage}

---
<sub>{day} · imba-radar</sub>
"""


def render_index(branch_name: str, cards: list[RepoCandidate], day: str) -> str:
    branch = get_branch(branch_name)
    title = branch.title if branch else branch_name
    blurb = branch.blurb if branch else ""
    lines = [
        f"# {title}",
        "",
        f"{blurb}",
        "",
        f"_Обновлено {day} UTC_",
        "",
        "| Репо | ★ | Сегодня | Score | Язык |",
        "|---|---:|---:|---:|---|",
    ]
    for c in cards:
        today = _fmt_int(c.stars_today) if c.stars_today else "-"
        lines.append(
            f"| [{c.full_name}](./{day}/{c.slug}.md) | {_fmt_int(c.stars)} | {today} | {c.score} | {c.language or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_root_readme(days_note: str) -> str:
    return f"""# imba

Живая витрина GitHub-имбы.

Контент лежит в ветках:

- `imba/hot` - вирусное и резкий рост
- `imba/new` - свежие репозитории
- `imba/ai` - LLM / agents / MCP
- `imba/bots` - Telegram / Discord боты
- `imba/tools` - CLI и DX
- `imba/releases` - релизы
- `imba/latest` - общая лента

`main` - только код радара, не лента.

{days_note}
"""


def _fmt_int(n: int | None) -> str:
    if n is None:
        return "0"
    return f"{n:,}".replace(",", " ")
