from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings


def _resolve_database_url() -> str:
    if settings.database_url:
        return settings.database_url
    sqlite_path = Path(settings.sqlite_db_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{sqlite_path}"


DATABASE_URL = _resolve_database_url()
Path(settings.export_dir).mkdir(parents=True, exist_ok=True)

engine_kwargs: dict = {"future": True, "pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine: Engine = create_engine(DATABASE_URL, **engine_kwargs)
metadata = MetaData()

webhook_events = Table(
    "webhook_events",
    metadata,
    Column("webhook_event_id", String(255), primary_key=True),
    Column("event_type", String(50)),
    Column("raw_payload", Text),
    Column("created_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
)

signups = Table(
    "signups",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("uid", String(255), nullable=False),
    Column("name", String(255), nullable=False),
    Column("group_id", String(255)),
    Column("shift", String(255), nullable=False),
    Column("signup_at", String(32), nullable=False),
    Column("signup_window", String(50), nullable=False),
    Column("status", String(50), nullable=False),
    Column("work_date", String(16), nullable=False),
    Column("created_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
    UniqueConstraint("uid", "work_date", name="uq_signups_uid_work_date"),
)

attendance_records = Table(
    "attendance_records",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("date", String(16), nullable=False),
    Column("uid", String(255), nullable=False),
    Column("name", String(255), nullable=False),
    Column("group_id", String(255)),
    Column("shift", String(255), server_default=""),
    Column("in_time", String(16), server_default=""),
    Column("break_start", String(16), server_default=""),
    Column("break_end", String(16), server_default=""),
    Column("out_time", String(16), server_default=""),
    Column("break_min", Integer),
    Column("work_min", Integer),
    Column("net_min", Integer),
    Column("remark", String(255), server_default=""),
    Column("status", String(50), nullable=False, server_default="未上班打卡"),
    Column("created_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
    UniqueConstraint("uid", "date", name="uq_attendance_records_uid_date"),
)

attendance_events = Table(
    "attendance_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("uid", String(255), nullable=False),
    Column("group_id", String(255)),
    Column("work_date", String(16), nullable=False),
    Column("action", String(50), nullable=False),
    Column("event_time", String(32), nullable=False),
    Column("created_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
)

bonus_rules = Table(
    "bonus_rules",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("rule_date", String(16)),
    Column("source_shift", String(255), nullable=False),
    Column("shift_alias", String(255)),
    Column("bonus_per_hour", Float),
    Column("source_sheet", String(255)),
    Column("is_active", Integer, nullable=False, server_default="1"),
    Column("created_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
)

system_logs = Table(
    "system_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("log_time", String(16), nullable=False),
    Column("level", String(16), nullable=False),
    Column("tag", String(255), nullable=False),
    Column("message", Text, nullable=False),
    Column("created_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
)

employees = Table(
    "employees",
    metadata,
    Column("uid", String(255), primary_key=True),
    Column("name", String(255), nullable=False, server_default=""),
    Column("group_id", String(255), server_default=""),
    Column("role", String(32), nullable=False, server_default="staff"),
    Column("status", String(32), nullable=False, server_default="active"),
    Column("source", String(255), server_default="首次互動自動建檔"),
    Column("latest_shift", String(255), server_default=""),
    Column("note", Text, server_default=""),
    Column("created_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", String(32), server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_signups_work_date", signups.c.work_date)
Index("idx_attendance_date", attendance_records.c.date)
Index("idx_bonus_rules_rule_date", bonus_rules.c.rule_date)
Index("idx_employees_group_id", employees.c.group_id)
Index("idx_employees_role", employees.c.role)
Index("idx_employees_status", employees.c.status)


@contextmanager
def connection() -> Iterator[Connection]:
    with engine.begin() as conn:
        yield conn


def init_db() -> None:
    metadata.create_all(engine)
