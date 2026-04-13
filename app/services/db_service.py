from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.config import settings
from app.core.db import connection

TZ = ZoneInfo(settings.timezone)


def _row_to_dict(row: Any | None) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return dict(row._mapping)


class DatabaseService:
    def is_duplicate_webhook(self, webhook_event_id: str) -> bool:
        if not webhook_event_id:
            return False
        with connection() as conn:
            row = conn.execute(
                text("SELECT webhook_event_id FROM webhook_events WHERE webhook_event_id = :webhook_event_id"),
                {"webhook_event_id": webhook_event_id},
            ).first()
            return row is not None

    def save_webhook_event(self, webhook_event_id: str, event_type: str, raw_payload: str) -> None:
        if not webhook_event_id or self.is_duplicate_webhook(webhook_event_id):
            return
        with connection() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO webhook_events (webhook_event_id, event_type, raw_payload)
                    VALUES (:webhook_event_id, :event_type, :raw_payload)
                    """
                ),
                {"webhook_event_id": webhook_event_id, "event_type": event_type, "raw_payload": raw_payload},
            )

    def add_log(self, level: str, tag: str, message: str) -> None:
        now_text = datetime.now(TZ).strftime("%H:%M:%S")
        with connection() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO system_logs (log_time, level, tag, message)
                    VALUES (:log_time, :level, :tag, :message)
                    """
                ),
                {"log_time": now_text, "level": level.upper(), "tag": tag, "message": message[:4000]},
            )

    def upsert_signup(self, uid: str, name: str, group_id: str, shift: str, signup_at: str, signup_window: str, work_date: str) -> str:
        with connection() as conn:
            existing = conn.execute(
                text("SELECT id FROM signups WHERE uid = :uid AND work_date = :work_date"),
                {"uid": uid, "work_date": work_date},
            ).first()
            if existing:
                conn.execute(
                    text(
                        """
                        UPDATE signups
                        SET name = :name, group_id = :group_id, shift = :shift, signup_at = :signup_at,
                            signup_window = :signup_window, status = :status, updated_at = CURRENT_TIMESTAMP
                        WHERE uid = :uid AND work_date = :work_date
                        """
                    ),
                    {
                        "name": name,
                        "group_id": group_id,
                        "shift": shift,
                        "signup_at": signup_at,
                        "signup_window": signup_window,
                        "status": "已更新班別",
                        "uid": uid,
                        "work_date": work_date,
                    },
                )
                return "update"

            conn.execute(
                text(
                    """
                    INSERT INTO signups (uid, name, group_id, shift, signup_at, signup_window, status, work_date)
                    VALUES (:uid, :name, :group_id, :shift, :signup_at, :signup_window, :status, :work_date)
                    """
                ),
                {
                    "uid": uid,
                    "name": name,
                    "group_id": group_id,
                    "shift": shift,
                    "signup_at": signup_at,
                    "signup_window": signup_window,
                    "status": "已登記",
                    "work_date": work_date,
                },
            )
            return "insert"

    def import_signup(
        self,
        uid: str,
        name: str,
        shift: str,
        signup_at: str,
        group_id: str = "",
        signup_window: str = "21:00 - 00:00",
        work_date: str = "",
    ) -> str:
        work_date = work_date or (signup_at[:10] if signup_at else "")
        if not uid or not work_date:
            return "skip"
        return self.upsert_signup(uid, name, group_id, shift, signup_at or f"{work_date} 00:00:00", signup_window, work_date)

    def list_all_signups(self) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute(text("SELECT * FROM signups ORDER BY work_date DESC, signup_at DESC, uid")).mappings().all()
        return [dict(r) for r in rows]

    def get_latest_signup_date(self) -> str | None:
        with connection() as conn:
            row = conn.execute(text("SELECT MAX(work_date) AS latest FROM signups")).mappings().first()
        return row["latest"] if row and row["latest"] else None

    def get_shift_for_date(self, uid: str, work_date: str) -> str:
        with connection() as conn:
            row = conn.execute(
                text("SELECT shift FROM signups WHERE uid = :uid AND work_date = :work_date"),
                {"uid": uid, "work_date": work_date},
            ).mappings().first()
        return row["shift"] if row else ""

    def get_attendance_record(self, uid: str, date_key: str) -> Optional[dict[str, Any]]:
        with connection() as conn:
            row = conn.execute(
                text("SELECT * FROM attendance_records WHERE uid = :uid AND date = :date_key"),
                {"uid": uid, "date_key": date_key},
            ).first()
        return _row_to_dict(row)

    def create_attendance_record(self, date_key: str, uid: str, name: str, group_id: str, shift: str) -> None:
        with connection() as conn:
            existing = conn.execute(
                text("SELECT id FROM attendance_records WHERE uid = :uid AND date = :date_key"),
                {"uid": uid, "date_key": date_key},
            ).first()
            if existing:
                return
            conn.execute(
                text(
                    """
                    INSERT INTO attendance_records (date, uid, name, group_id, shift)
                    VALUES (:date_key, :uid, :name, :group_id, :shift)
                    """
                ),
                {"date_key": date_key, "uid": uid, "name": name, "group_id": group_id, "shift": shift},
            )

    def upsert_attendance_record(
        self,
        date_key: str,
        uid: str,
        name: str,
        group_id: str,
        shift: str = "",
        in_time: str = "",
        break_start: str = "",
        break_end: str = "",
        out_time: str = "",
        break_min: Any = None,
        work_min: Any = None,
        net_min: Any = None,
        remark: str = "",
        status: str = "未上班打卡",
    ) -> str:
        params = {
            "date_key": date_key,
            "uid": uid,
            "name": name,
            "group_id": group_id,
            "shift": shift,
            "in_time": in_time,
            "break_start": break_start,
            "break_end": break_end,
            "out_time": out_time,
            "break_min": break_min,
            "work_min": work_min,
            "net_min": net_min,
            "remark": remark,
            "status": status,
        }
        with connection() as conn:
            existing = conn.execute(
                text("SELECT id FROM attendance_records WHERE uid = :uid AND date = :date_key"),
                {"uid": uid, "date_key": date_key},
            ).first()
            if existing:
                conn.execute(
                    text(
                        """
                        UPDATE attendance_records
                        SET name = :name, group_id = :group_id, shift = :shift, in_time = :in_time,
                            break_start = :break_start, break_end = :break_end, out_time = :out_time,
                            break_min = :break_min, work_min = :work_min, net_min = :net_min,
                            remark = :remark, status = :status, updated_at = CURRENT_TIMESTAMP
                        WHERE uid = :uid AND date = :date_key
                        """
                    ),
                    params,
                )
                return "update"

            conn.execute(
                text(
                    """
                    INSERT INTO attendance_records (
                        date, uid, name, group_id, shift, in_time, break_start, break_end,
                        out_time, break_min, work_min, net_min, remark, status
                    )
                    VALUES (
                        :date_key, :uid, :name, :group_id, :shift, :in_time, :break_start, :break_end,
                        :out_time, :break_min, :work_min, :net_min, :remark, :status
                    )
                    """
                ),
                params,
            )
            return "insert"

    def add_attendance_event(self, uid: str, group_id: str, work_date: str, action: str, event_time: str) -> None:
        with connection() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO attendance_events (uid, group_id, work_date, action, event_time)
                    VALUES (:uid, :group_id, :work_date, :action, :event_time)
                    """
                ),
                {"uid": uid, "group_id": group_id, "work_date": work_date, "action": action, "event_time": event_time},
            )

    def list_all_attendance(self) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute(text("SELECT * FROM attendance_records ORDER BY date DESC, uid")).mappings().all()
        return [dict(r) for r in rows]

    def get_latest_attendance_date(self) -> str | None:
        with connection() as conn:
            row = conn.execute(text("SELECT MAX(date) AS latest FROM attendance_records")).mappings().first()
        return row["latest"] if row and row["latest"] else None

    def update_attendance_fields(self, uid: str, date_key: str, **fields: Any) -> None:
        if not fields:
            return
        assignments = ", ".join([f"{k} = :{k}" for k in fields.keys()]) + ", updated_at = CURRENT_TIMESTAMP"
        params = {**fields, "uid": uid, "date_key": date_key}
        with connection() as conn:
            conn.execute(
                text(f"UPDATE attendance_records SET {assignments} WHERE uid = :uid AND date = :date_key"),
                params,
            )

    def update_attendance_shift(self, uid: str, date_key: str, shift: str, remark: str | None = None) -> None:
        params: dict[str, Any] = {
            "uid": uid,
            "date_key": date_key,
            "shift": shift,
        }
        assignments = "shift = :shift, updated_at = CURRENT_TIMESTAMP"
        if remark is not None:
            assignments = "shift = :shift, remark = :remark, updated_at = CURRENT_TIMESTAMP"
            params["remark"] = remark
        with connection() as conn:
            conn.execute(
                text(f"UPDATE attendance_records SET {assignments} WHERE uid = :uid AND date = :date_key"),
                params,
            )

    def list_signups(self, target_date: str) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, uid, name, group_id, shift, signup_at, signup_window, status
                    FROM signups WHERE work_date = :target_date ORDER BY signup_at DESC
                    """
                ),
                {"target_date": target_date},
            ).mappings().all()
        return [
            {
                "id": r["id"],
                "uid": r["uid"],
                "name": r["name"],
                "groupId": r["group_id"],
                "shift": r["shift"],
                "signupAt": r["signup_at"],
                "window": r["signup_window"],
                "status": r["status"],
            }
            for r in rows
        ]

    def list_attendance(self, target_date: str) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, date, uid, name, group_id, shift, in_time, break_start, break_end, out_time,
                           break_min, work_min, net_min, remark, status
                    FROM attendance_records
                    WHERE date = :target_date
                    ORDER BY COALESCE(in_time, ''), uid
                    """
                ),
                {"target_date": target_date},
            ).mappings().all()
        return [
            {
                "id": r["id"],
                "date": r["date"],
                "uid": r["uid"],
                "name": r["name"],
                "groupId": r["group_id"],
                "shift": r["shift"] or "",
                "in": r["in_time"] or "",
                "breakStart": r["break_start"] or "",
                "breakEnd": r["break_end"] or "",
                "out": r["out_time"] or "",
                "breakMin": r["break_min"] if r["break_min"] is not None else "",
                "workMin": r["work_min"] if r["work_min"] is not None else "",
                "netMin": r["net_min"] if r["net_min"] is not None else "",
                "remark": r["remark"] or "",
                "status": r["status"],
            }
            for r in rows
        ]

    def list_logs(self, limit: int = 30) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT log_time, level, tag, message
                    FROM system_logs
                    ORDER BY id DESC
                    LIMIT :limit_rows
                    """
                ),
                {"limit_rows": limit},
            ).mappings().all()
        return [{"time": r["log_time"], "level": r["level"], "tag": r["tag"], "message": r["message"]} for r in rows]

    def replace_bonus_rules(self, rules: list[dict[str, Any]]) -> int:
        with connection() as conn:
            conn.execute(text("DELETE FROM bonus_rules"))
            for r in rules:
                conn.execute(
                    text(
                        """
                        INSERT INTO bonus_rules (rule_date, source_shift, shift_alias, bonus_per_hour, source_sheet, is_active)
                        VALUES (:rule_date, :source_shift, :shift_alias, :bonus_per_hour, :source_sheet, :is_active)
                        """
                    ),
                    {
                        "rule_date": r.get("rule_date") or "",
                        "source_shift": r.get("source_shift") or "",
                        "shift_alias": r.get("shift_alias") or "",
                        "bonus_per_hour": r.get("bonus_per_hour"),
                        "source_sheet": r.get("source_sheet") or "",
                        "is_active": 1 if r.get("is_active", True) else 0,
                    },
                )
        return len(rules)

    def list_bonus_rules(self, target_date: str | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT id, rule_date, source_shift, shift_alias, bonus_per_hour, source_sheet
            FROM bonus_rules
            WHERE is_active = 1
        """
        params: dict[str, Any] = {}
        if target_date:
            sql += " AND (rule_date = :target_date OR rule_date = '')"
            params["target_date"] = target_date
        sql += " ORDER BY COALESCE(rule_date, '') DESC, id DESC"
        with connection() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]

    def lookup_bonus_per_hour(self, target_date: str, shift_alias: str) -> float | None:
        with connection() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT bonus_per_hour FROM bonus_rules
                    WHERE is_active = 1 AND shift_alias = :shift_alias
                      AND (rule_date = :target_date OR rule_date = '')
                    ORDER BY CASE WHEN rule_date = :target_date THEN 0 ELSE 1 END, id DESC
                    LIMIT 1
                    """
                ),
                {"shift_alias": shift_alias, "target_date": target_date},
            ).mappings().first()
        return float(row["bonus_per_hour"]) if row and row["bonus_per_hour"] is not None else None

    def upsert_employee(
        self,
        uid: str,
        name: str,
        group_id: str,
        role: str = "staff",
        status: str = "active",
        source: str = "首次互動自動建檔",
    ) -> None:
        with connection() as conn:
            existing = conn.execute(
                text("SELECT uid, name, group_id FROM employees WHERE uid = :uid"),
                {"uid": uid},
            ).mappings().first()
            if existing:
                conn.execute(
                    text(
                        """
                        UPDATE employees
                        SET
                            name = CASE
                                WHEN COALESCE(name, '') = '' THEN :name
                                ELSE name
                            END,
                            group_id = :group_id,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE uid = :uid
                        """
                    ),
                    {
                        "uid": uid,
                        "name": name or existing["name"] or "",
                        "group_id": group_id or existing["group_id"] or "",
                    },
                )
                return

            conn.execute(
                text(
                    """
                    INSERT INTO employees (uid, name, group_id, role, status, source)
                    VALUES (:uid, :name, :group_id, :role, :status, :source)
                    """
                ),
                {"uid": uid, "name": name, "group_id": group_id, "role": role, "status": status, "source": source},
            )

    def update_employee_latest_shift(self, uid: str, latest_shift: str) -> None:
        with connection() as conn:
            conn.execute(
                text("UPDATE employees SET latest_shift = :latest_shift, updated_at = CURRENT_TIMESTAMP WHERE uid = :uid"),
                {"latest_shift": latest_shift, "uid": uid},
            )

    def list_employees(self) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT uid, name, group_id, role, status, source, latest_shift, note
                    FROM employees
                    ORDER BY updated_at DESC, uid
                    """
                )
            ).mappings().all()
        return [dict(r) for r in rows]

    def get_employee(self, uid: str) -> Optional[dict[str, Any]]:
        with connection() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT uid, name, group_id, role, status, source, latest_shift, note
                    FROM employees
                    WHERE uid = :uid
                    """
                ),
                {"uid": uid},
            ).mappings().first()
        return dict(row) if row else None

    def update_employee_role(self, uid: str, role: str) -> None:
        with connection() as conn:
            conn.execute(
                text("UPDATE employees SET role = :role, updated_at = CURRENT_TIMESTAMP WHERE uid = :uid"),
                {"role": role, "uid": uid},
            )

    def update_employee_name(self, uid: str, name: str) -> None:
        with connection() as conn:
            conn.execute(
                text("UPDATE employees SET name = :name, updated_at = CURRENT_TIMESTAMP WHERE uid = :uid"),
                {"name": name, "uid": uid},
            )
            conn.execute(
                text("UPDATE signups SET name = :name, updated_at = CURRENT_TIMESTAMP WHERE uid = :uid"),
                {"name": name, "uid": uid},
            )
            conn.execute(
                text("UPDATE attendance_records SET name = :name, updated_at = CURRENT_TIMESTAMP WHERE uid = :uid"),
                {"name": name, "uid": uid},
            )

    def update_employee_status(self, uid: str, status: str) -> None:
        with connection() as conn:
            conn.execute(
                text("UPDATE employees SET status = :status, updated_at = CURRENT_TIMESTAMP WHERE uid = :uid"),
                {"status": status, "uid": uid},
            )

    def update_employee_note(self, uid: str, note: str) -> None:
        with connection() as conn:
            conn.execute(
                text("UPDATE employees SET note = :note, updated_at = CURRENT_TIMESTAMP WHERE uid = :uid"),
                {"note": note, "uid": uid},
            )
