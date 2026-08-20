from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from imba_radar.config.branches import BRANCHES, branch_names
from imba_radar.config.settings import Settings
from imba_radar.format.card import render_card, render_index, render_root_readme
from imba_radar.github.models import RepoCandidate
from imba_radar.preview.fetch import PreviewFetcher

log = logging.getLogger(__name__)


class BranchPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo_dir = settings.workspace_dir / settings.github_repo
        self.preview = PreviewFetcher()

    def ensure_local_repo(self) -> None:
        if (self.repo_dir / ".git").exists():
            self._git("remote", "set-url", "origin", self.settings.clone_url)
            try:
                self._git("fetch", "origin", "--prune")
            except Exception as e:
                log.warning("fetch origin: %s", e)
            return

        self.settings.workspace_dir.mkdir(parents=True, exist_ok=True)
        if self.repo_dir.exists():
            # broken partial dir
            import shutil
            shutil.rmtree(self.repo_dir)

        try:
            subprocess.run(
                ["git", "clone", self.settings.clone_url, str(self.repo_dir)],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            log.warning("clone failed (%s), init local", e)
            self.repo_dir.mkdir(parents=True, exist_ok=True)
            self._git("init", "-b", "main")
            self._git("remote", "add", "origin", self.settings.clone_url)

        self._ensure_root_commit()
        for name in branch_names():
            exists = self._git_out("branch", "--list", name).strip()
            remote = ""
            try:
                remote = self._git_out("branch", "-r", "--list", f"origin/{name}").strip()
            except Exception:
                remote = ""
            if not exists and remote:
                self._git("checkout", "-b", name, f"origin/{name}")
            elif not exists:
                # named branches need an existing HEAD commit
                self._git("branch", name, "HEAD")
        self._push_all_best_effort()

    def _ensure_root_commit(self) -> None:
        has_commit = True
        try:
            self._git_out("rev-parse", "HEAD")
        except Exception:
            has_commit = False
        if has_commit:
            return
        # empty repo / no default branch yet
        try:
            self._git("checkout", "-B", "main")
        except Exception:
            self._git("checkout", "--orphan", "main")
        readme = self.repo_dir / "README.md"
        if not readme.exists():
            readme.write_text(
                render_root_readme("Автопубликация через imba-radar."),
                encoding="utf-8",
            )
        self._git("add", "README.md")
        self._commit("chore: init imba feed")
    async def publish(self, cards: list[RepoCandidate], day: str) -> int:
        if not cards:
            return 0
        published = 0
        by_branch: dict[str, list[RepoCandidate]] = {}
        for c in cards:
            by_branch.setdefault(c.branch, []).append(c)
            by_branch.setdefault("imba/latest", []).append(c)

        for branch, items in by_branch.items():
            uniq: dict[str, RepoCandidate] = {}
            for c in items:
                uniq[c.full_name] = c
            n = await self._publish_branch(branch, list(uniq.values()), day)
            published += n
        return published

    async def _publish_branch(self, branch: str, cards: list[RepoCandidate], day: str) -> int:
        self._checkout(branch)
        day_dir = self.repo_dir / day
        assets = self.repo_dir / "assets"
        day_dir.mkdir(parents=True, exist_ok=True)
        assets.mkdir(parents=True, exist_ok=True)

        written = 0
        for c in sorted(cards, key=lambda x: x.score, reverse=True):
            await self.preview.fetch_to(c, assets / c.slug)
            path = day_dir / f"{c.slug}.md"
            path.write_text(render_card(c, day), encoding="utf-8")
            written += 1

        # rebuild index from existing day cards + new
        index_cards = self._load_day_meta(branch, day, cards)
        (self.repo_dir / "_index.md").write_text(
            render_index(branch, index_cards, day),
            encoding="utf-8",
        )
        spec = next((b for b in BRANCHES if b.name == branch), None)
        title = spec.title if spec else branch
        self._git("add", "-A")
        if self._git_out("status", "--porcelain").strip():
            names = ", ".join(c.full_name for c in cards[:5])
            self._commit(f"imba({title}): {len(cards)} cards - {names}")
            self._push_best_effort(branch)
        return written

    def _load_day_meta(
        self,
        branch: str,
        day: str,
        fresh: list[RepoCandidate],
    ) -> list[RepoCandidate]:
        # Prefer fresh list sorted; index keeps this tick's view clean
        return sorted(fresh, key=lambda c: c.score, reverse=True)[:40]

    def _checkout(self, branch: str) -> None:
        # ensure branch exists locally
        exists = self._git_out("branch", "--list", branch).strip()
        if not exists:
            self._git("branch", branch)
        self._git("checkout", branch)

    def _commit(self, message: str) -> None:
        env = {
            "GIT_AUTHOR_NAME": self.settings.git_author_name,
            "GIT_AUTHOR_EMAIL": self.settings.git_author_email,
            "GIT_COMMITTER_NAME": self.settings.git_author_name,
            "GIT_COMMITTER_EMAIL": self.settings.git_author_email,
        }
        self._git("commit", "-m", message, env=env)

    def _push_best_effort(self, branch: str) -> None:
        try:
            self._git("push", "-u", "origin", branch)
            log.info("pushed %s", branch)
        except Exception as e:
            log.warning("push skipped (%s): %s", branch, e)

    def _push_all_best_effort(self) -> None:
        try:
            self._git("push", "-u", "origin", "main")
        except Exception as e:
            log.warning("push main skipped: %s", e)
        for name in branch_names():
            self._push_best_effort(name)

    def _git(self, *args: str, env: dict[str, str] | None = None) -> None:
        out = self._git_out(*args, env=env)
        if out:
            log.debug("git %s -> %s", " ".join(args), out[:200])

    def _git_out(self, *args: str, env: dict[str, str] | None = None) -> str:
        import os

        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        p = subprocess.run(
            ["git", *args],
            cwd=self.repo_dir,
            env=full_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if p.returncode != 0:
            raise RuntimeError(p.stderr.strip() or p.stdout.strip() or f"git {' '.join(args)}")
        return p.stdout
