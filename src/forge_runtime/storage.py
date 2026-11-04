"""SQLite persistence for local development and single-process execution."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from forge_runtime.models import RunRecord, RuntimeEvent, TaskRecord


class SQLiteStore:
    def __init__(self, database_url: str) -> None:
        prefix = "sqlite:///"
        if not database_url.startswith(prefix):
            raise ValueError("Initial storage backend supports sqlite:/// URLs only.")
        raw = Path(database_url[len(prefix):])
        self.path = raw if raw.is_absolute() else (Path.cwd() / raw).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY, goal TEXT NOT NULL, status TEXT NOT NULL,
                  plan_json TEXT, summary TEXT, created_at TEXT NOT NULL,
                  started_at TEXT, finished_at TEXT);
                CREATE TABLE IF NOT EXISTS tasks (
                  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, title TEXT NOT NULL,
                  agent TEXT NOT NULL, status TEXT NOT NULL, attempt INTEGER NOT NULL,
                  output TEXT, error TEXT, started_at TEXT, finished_at TEXT,
                  FOREIGN KEY(run_id) REFERENCES runs(id));
                CREATE TABLE IF NOT EXISTS events (
                  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT,
                  level TEXT NOT NULL, event_type TEXT NOT NULL, message TEXT NOT NULL,
                  data_json TEXT NOT NULL, created_at TEXT NOT NULL,
                  FOREIGN KEY(run_id) REFERENCES runs(id));
                CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);
                CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, created_at);
            """)

    def save_run(self, run: RunRecord) -> None:
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?)", (
                run.id, run.goal, run.status.value,
                run.plan.model_dump_json() if run.plan else None, run.summary,
                run.created_at.isoformat(), run.started_at.isoformat() if run.started_at else None,
                run.finished_at.isoformat() if run.finished_at else None))

    def save_task(self, task: TaskRecord) -> None:
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)", (
                task.id, task.run_id, task.title, task.agent, task.status.value, task.attempt,
                task.output, task.error, task.started_at.isoformat() if task.started_at else None,
                task.finished_at.isoformat() if task.finished_at else None))

    def add_event(self, event: RuntimeEvent) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?)", (
                event.id, event.run_id, event.task_id, event.level.value, event.event_type,
                event.message, json.dumps(event.data, default=str), event.created_at.isoformat()))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["tasks"] = [dict(x) for x in db.execute("SELECT * FROM tasks WHERE run_id=? ORDER BY rowid", (run_id,))]
            result["events"] = [dict(x) for x in db.execute("SELECT * FROM events WHERE run_id=? ORDER BY created_at", (run_id,))]
            return result

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT id,goal,status,created_at,finished_at FROM runs ORDER BY created_at DESC LIMIT ?", (limit,))]
