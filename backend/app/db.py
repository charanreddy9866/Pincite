"""SQLite persistence. One file, no server: easy to run locally and inside one Cloud Run container."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY,
    case_id     INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    exhibit_no  INTEGER NOT NULL,
    filename    TEXT NOT NULL,
    pages       INTEGER NOT NULL,
    ocr_pages   INTEGER NOT NULL DEFAULT 0,
    redactions  TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no     INTEGER NOT NULL,
    text        TEXT NOT NULL,
    PRIMARY KEY (document_id, page_no)
);
CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY,
    case_id     INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no     INTEGER NOT NULL,
    text        TEXT NOT NULL,
    embedding   BLOB
);
CREATE INDEX IF NOT EXISTS chunks_case ON chunks(case_id);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    case_id     INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    date        TEXT NOT NULL,
    precision   TEXT NOT NULL,
    description TEXT NOT NULL,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no     INTEGER NOT NULL,
    quote       TEXT NOT NULL,
    method      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id          INTEGER PRIMARY KEY,
    ts          TEXT NOT NULL,
    case_id     INTEGER,
    action      TEXT NOT NULL,
    detail      TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.lock = threading.Lock()

    def execute(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        with self.lock:
            self.conn.executemany(sql, rows)
            self.conn.commit()

    def all(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute(sql, params).fetchone()

    def audit(self, case_id: int | None, action: str, **detail) -> None:
        self.execute(
            "INSERT INTO audit (ts, case_id, action, detail) VALUES (?, ?, ?, ?)",
            (now(), case_id, action, json.dumps(detail)),
        )


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        from .config import get_settings

        _db = Database(get_settings().database_path)
    return _db
