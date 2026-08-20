from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BranchSpec:
    name: str
    title: str
    blurb: str
    topics: tuple[str, ...]
    keywords: tuple[str, ...]


BRANCHES: tuple[BranchSpec, ...] = (
    BranchSpec(
        name="imba/hot",
        title="Hot",
        blurb="Резкий рост и вирусные репозитории",
        topics=("trending",),
        keywords=("viral", "hot", "boom"),
    ),
    BranchSpec(
        name="imba/new",
        title="New",
        blurb="Свежие репозитории последних дней",
        topics=("new",),
        keywords=("fresh", "new"),
    ),
    BranchSpec(
        name="imba/ai",
        title="AI",
        blurb="LLM, agents, RAG, MCP",
        topics=("ai", "llm", "machine-learning", "mcp"),
        keywords=(
            "llm", "openai", "anthropic", "agent", "rag", "mcp",
            "transformer", "diffusion", "langchain", "ollama",
        ),
    ),
    BranchSpec(
        name="imba/bots",
        title="Bots",
        blurb="Telegram, Discord и messaging-боты",
        topics=("telegram-bot", "discord-bot", "bot"),
        keywords=("telegram", "discord", "bot", "grammy", "aiogram", "telegraf"),
    ),
    BranchSpec(
        name="imba/tools",
        title="Tools",
        blurb="CLI, DX, библиотеки и утилиты",
        topics=("cli", "devtools", "library"),
        keywords=("cli", "sdk", "tool", "devtools", "framework", "library"),
    ),
    BranchSpec(
        name="imba/releases",
        title="Releases",
        blurb="Свежие релизы заметных проектов",
        topics=("release",),
        keywords=("release", "changelog"),
    ),
    BranchSpec(
        name="imba/latest",
        title="Latest",
        blurb="Живая лента всего отобранного",
        topics=("latest",),
        keywords=(),
    ),
)


def branch_names() -> list[str]:
    return [b.name for b in BRANCHES]


def get_branch(name: str) -> BranchSpec | None:
    for b in BRANCHES:
        if b.name == name:
            return b
    return None
