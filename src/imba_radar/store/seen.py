from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class SeenStore:
    def __init__(self, path: Path, ttl_days: int = 14) -> None:
        self.path = path
        self.ttl_sec = ttl_days * 86400
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen (
              full_name TEXT PRIMARY KEY,
              branch TEXT NOT NULL,
              score REAL NOT NULL,
              seen_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()
        self.purge()

    def purge(self) -> None:
        cut = time.time() - self.ttl_sec
        self._conn.execute("DELETE FROM seen WHERE seen_at < ?", (cut,))
        self._conn.commit()

    def has(self, full_name: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen WHERE full_name = ?",
            (full_name,),
        ).fetchone()
        return row is not None

    def mark(self, full_name: str, branch: str, score: float) -> None:
        self._conn.execute(
            """
            INSERT INTO seen(full_name, branch, score, seen_at)
            VALUES(?,?,?,?)
            ON CONFLICT(full_name) DO UPDATE SET
              branch=excluded.branch,
              score=excluded.score,
              seen_at=excluded.seen_at
            """,
            (full_name, branch, score, time.time()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class TickState:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            self._data = {"tick": 0, "last_trending_at": 0}
            self.save()
        else:
            self._data = json.loads(path.read_text(encoding="utf-8"))

    @property
    def tick(self) -> int:
        return int(self._data.get("tick") or 0)

    def bump(self) -> int:
        self._data["tick"] = self.tick + 1
        self.save()
        return self.tick

    def should_trending(self, every_ticks: int = 5) -> bool:
        return self.tick % every_ticks == 0

    def save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
