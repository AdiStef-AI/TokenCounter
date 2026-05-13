"""SQLite-backed storage for token usage history."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .tracker import SessionSummary, TurnUsage


DB_PATH = Path.home() / ".claude" / "tokencounter.db"


@contextmanager
def _connect(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                project_path TEXT,
                file_path TEXT,
                turns INTEGER,
                input_tokens INTEGER,
                cache_creation_tokens INTEGER,
                cache_read_tokens INTEGER,
                output_tokens INTEGER,
                models TEXT,
                start_time TEXT,
                end_time TEXT,
                synced_at TEXT
            );

            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                project_path TEXT,
                timestamp TEXT,
                model TEXT,
                input_tokens INTEGER,
                cache_creation_tokens INTEGER,
                cache_read_tokens INTEGER,
                output_tokens INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
            CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON turns(timestamp);
            CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_path);
        """)


def upsert_session(summary: SessionSummary, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute("""
            INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET
                turns=excluded.turns,
                input_tokens=excluded.input_tokens,
                cache_creation_tokens=excluded.cache_creation_tokens,
                cache_read_tokens=excluded.cache_read_tokens,
                output_tokens=excluded.output_tokens,
                models=excluded.models,
                start_time=excluded.start_time,
                end_time=excluded.end_time,
                synced_at=excluded.synced_at
        """, (
            summary.session_id,
            summary.project_path,
            str(summary.file_path),
            summary.turns,
            summary.input_tokens,
            summary.cache_creation_tokens,
            summary.cache_read_tokens,
            summary.output_tokens,
            ",".join(summary.models),
            summary.start_time.isoformat() if summary.start_time else None,
            summary.end_time.isoformat() if summary.end_time else None,
            datetime.utcnow().isoformat(),
        ))


def upsert_turns(turns: list[TurnUsage], db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with _connect(db_path) as conn:
        # Clear existing turns for this session before re-inserting
        if turns:
            conn.execute("DELETE FROM turns WHERE session_id = ?", (turns[0].session_id,))
        conn.executemany("""
            INSERT INTO turns
                (session_id, project_path, timestamp, model,
                 input_tokens, cache_creation_tokens, cache_read_tokens, output_tokens)
            VALUES (?,?,?,?,?,?,?,?)
        """, [
            (t.session_id, t.project_path, t.timestamp.isoformat(), t.model,
             t.input_tokens, t.cache_creation_tokens, t.cache_read_tokens, t.output_tokens)
            for t in turns
        ])


def query_sessions(
    project_filter: str | None = None,
    limit: int = 50,
    db_path: Path = DB_PATH,
) -> list[dict]:
    init_db(db_path)
    with _connect(db_path) as conn:
        if project_filter:
            rows = conn.execute("""
                SELECT * FROM sessions
                WHERE project_path LIKE ?
                ORDER BY end_time DESC LIMIT ?
            """, (f"%{project_filter}%", limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM sessions ORDER BY end_time DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def query_daily_totals(days: int = 30, db_path: Path = DB_PATH) -> list[dict]:
    """Aggregate turns by day for trend/forecast."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("""
            SELECT
                date(timestamp) AS day,
                SUM(input_tokens) AS input_tokens,
                SUM(cache_creation_tokens) AS cache_creation_tokens,
                SUM(cache_read_tokens) AS cache_read_tokens,
                SUM(output_tokens) AS output_tokens,
                SUM(input_tokens + cache_creation_tokens + cache_read_tokens + output_tokens) AS total_tokens,
                COUNT(*) AS turn_count
            FROM turns
            WHERE timestamp >= date('now', ?)
            GROUP BY day
            ORDER BY day
        """, (f"-{days} days",)).fetchall()
        return [dict(r) for r in rows]


def get_overall_totals(db_path: Path = DB_PATH) -> dict:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("""
            SELECT
                COUNT(DISTINCT session_id) AS sessions,
                SUM(turns) AS turns,
                SUM(input_tokens) AS input_tokens,
                SUM(cache_creation_tokens) AS cache_creation_tokens,
                SUM(cache_read_tokens) AS cache_read_tokens,
                SUM(output_tokens) AS output_tokens
            FROM sessions
        """).fetchone()
        return dict(row) if row else {}
