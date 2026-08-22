"""Small, durable SQLite audit store. One application worker is supported."""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    status TEXT NOT NULL, data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                CREATE INDEX IF NOT EXISTS events_run_seq ON events(run_id, seq);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def create(self, run_id: str, data: dict) -> None:
        timestamp = now()
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES (?,?,?,?,?)",
                       (run_id, timestamp, timestamp, "queued", json.dumps(data)))

    def get(self, run_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return {**json.loads(row["data"]), "id": row["id"], "status": row["status"],
                "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def update(self, run_id: str, *, status: str | None = None, **values) -> None:
        current = self.get(run_id)
        old_status = current.pop("status")
        for key in ("id", "created_at", "updated_at"):
            current.pop(key)
        current.update(values)
        with self.connect() as db:
            db.execute("UPDATE runs SET status=?, updated_at=?, data=? WHERE id=?",
                       (status or old_status, now(), json.dumps(current), run_id))

    def recent(self, limit: int = 20) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT id FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self.get(row["id"]) for row in rows]

    def count(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT count(*) FROM runs").fetchone()[0]

    def event(self, run_id: str, kind: str, data: dict) -> int:
        with self.connect() as db:
            cursor = db.execute("INSERT INTO events(run_id,created_at,kind,data) VALUES (?,?,?,?)",
                                (run_id, now(), kind, json.dumps(data)))
            return int(cursor.lastrowid)

    def events(self, run_id: str, after: int = 0) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT 500",
                              (run_id, after)).fetchall()
        return [{"seq": r["seq"], "kind": r["kind"], "created_at": r["created_at"],
                 "data": json.loads(r["data"])} for r in rows]

    def interrupt_unfinished(self) -> None:
        with self.connect() as db:
            db.execute("UPDATE runs SET status='interrupted',updated_at=? WHERE status IN ('queued','running','awaiting_approval')", (now(),))
