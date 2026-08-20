from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_owner: str = Field(default="swensi17", alias="GITHUB_OWNER")
    github_repo: str = Field(default="imba", alias="GITHUB_REPO")

    poll_interval_sec: int = Field(default=60, alias="POLL_INTERVAL_SEC", ge=30, le=600)
    max_cards_per_tick: int = Field(default=8, alias="MAX_CARDS_PER_TICK", ge=1, le=30)
    min_score: float = Field(default=42.0, alias="MIN_SCORE")
    lang: str = Field(default="ru", alias="LANG")

    git_author_name: str = Field(default="imba-radar", alias="GIT_AUTHOR_NAME")
    git_author_email: str = Field(
        default="imba-radar@users.noreply.github.com",
        alias="GIT_AUTHOR_EMAIL",
    )

    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    workspace_dir: Path = Field(default=Path("./workspace"), alias="WORKSPACE_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_owner_ids: str = Field(default="", alias="TELEGRAM_OWNER_IDS")

    @property
    def owner_ids(self) -> list[int]:
        out: list[int] = []
        for part in self.telegram_owner_ids.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(int(part))
            except ValueError:
                continue
        return out

    @property
    def repo_full_name(self) -> str:
        return f"{self.github_owner}/{self.github_repo}"

    @property
    def clone_url(self) -> str:
        if self.github_token:
            return (
                f"https://x-access-token:{self.github_token}"
                f"@github.com/{self.github_owner}/{self.github_repo}.git"
            )
        return f"https://github.com/{self.github_owner}/{self.github_repo}.git"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    return Settings()
