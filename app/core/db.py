from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import settings


DB_PATH = Path(settings.sqlite_db_path)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
Path(settings.export_dir).mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS webhook_events (
                webhook_event_id TEXT PRIMARY KEY,
                event_type TEXT,
                raw_payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS signups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT NOT NULL,
                name TEXT NOT NULL,
                group_id TEXT,
                shift TEXT NOT NULL,
                signup_at TEXT NOT NULL,
                window TEXT NOT NULL,
                status TEXT NOT NULL,
                work_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(uid, work_date)
            );

            CREATE TABLE IF NOT EXISTS attendance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                uid TEXT NOT NULL,
                name TEXT NOT NULL,
                group_id TEXT,
                shift TEXT DEFAULT '',
                in_time TEXT DEFAULT '',
                break_start TEXT DEFAULT '',
                break_end TEXT DEFAULT '',
                out_time TEXT DEFAULT '',
                break_min INTEGER,
                work_min INTEGER,
                net_min INTEGER,
                remark TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT '未上班打卡',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(uid, date)
            );

            CREATE TABLE IF NOT EXISTS attendance_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT NOT NULL,
                group_id TEXT,
                work_date TEXT NOT NULL,
                action TEXT NOT NULL,
                event_time TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS bonus_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_date TEXT,
                source_shift TEXT NOT NULL,
                shift_alias TEXT,
                bonus_per_hour REAL,
                source_sheet TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_time TEXT NOT NULL,
                level TEXT NOT NULL,
                tag TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_signups_work_date ON signups(work_date);
            CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_records(date);
            CREATE INDEX IF NOT EXISTS idx_bonus_rules_rule_date ON bonus_rules(rule_date);
            """
        )
