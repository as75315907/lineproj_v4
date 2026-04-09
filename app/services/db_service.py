from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.db import connection

TZ = ZoneInfo(settings.timezone)


class DatabaseService:
    def is_duplicate_webhook(self, webhook_event_id: str) -> bool:
        if not webhook_event_id:
            return False
        with connection() as conn:
            row = conn.execute('SELECT webhook_event_id FROM webhook_events WHERE webhook_event_id = ?', (webhook_event_id,)).fetchone()
            return row is not None

    def save_webhook_event(self, webhook_event_id: str, event_type: str, raw_payload: str) -> None:
        if not webhook_event_id:
            return
        with connection() as conn:
            conn.execute('INSERT OR IGNORE INTO webhook_events (webhook_event_id, event_type, raw_payload) VALUES (?, ?, ?)', (webhook_event_id, event_type, raw_payload))

    def add_log(self, level: str, tag: str, message: str) -> None:
        now_text = datetime.now(TZ).strftime('%H:%M:%S')
        with connection() as conn:
            conn.execute('INSERT INTO system_logs (log_time, level, tag, message) VALUES (?, ?, ?, ?)', (now_text, level.upper(), tag, message[:4000]))

    def upsert_signup(self, uid: str, name: str, group_id: str, shift: str, signup_at: str, window: str, work_date: str) -> str:
        with connection() as conn:
            existing = conn.execute('SELECT id FROM signups WHERE uid = ? AND work_date = ?', (uid, work_date)).fetchone()
            if existing:
                conn.execute(
                    '''UPDATE signups
                       SET name = ?, group_id = ?, shift = ?, signup_at = ?, window = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE uid = ? AND work_date = ?''',
                    (name, group_id, shift, signup_at, window, '已更新班別', uid, work_date),
                )
                return 'update'
            conn.execute(
                '''INSERT INTO signups (uid, name, group_id, shift, signup_at, window, status, work_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (uid, name, group_id, shift, signup_at, window, '已登記', work_date),
            )
            return 'insert'

    def import_signup(self, uid: str, name: str, shift: str, signup_at: str, group_id: str = '', window: str = '21:00 - 00:00', work_date: str = '') -> str:
        work_date = work_date or (signup_at[:10] if signup_at else '')
        if not uid or not work_date:
            return 'skip'
        return self.upsert_signup(uid, name, group_id, shift, signup_at or f'{work_date} 00:00:00', window, work_date)

    def list_all_signups(self) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute('SELECT * FROM signups ORDER BY work_date DESC, signup_at DESC, uid').fetchall()
        return [dict(r) for r in rows]

    def get_latest_signup_date(self) -> str | None:
        with connection() as conn:
            row = conn.execute('SELECT MAX(work_date) AS latest FROM signups').fetchone()
        return row['latest'] if row and row['latest'] else None

    def get_shift_for_date(self, uid: str, work_date: str) -> str:
        with connection() as conn:
            row = conn.execute('SELECT shift FROM signups WHERE uid = ? AND work_date = ?', (uid, work_date)).fetchone()
            return row['shift'] if row else ''

    def get_attendance_record(self, uid: str, date_key: str) -> Optional[dict[str, Any]]:
        with connection() as conn:
            row = conn.execute('SELECT * FROM attendance_records WHERE uid = ? AND date = ?', (uid, date_key)).fetchone()
            return dict(row) if row else None

    def create_attendance_record(self, date_key: str, uid: str, name: str, group_id: str, shift: str) -> None:
        with connection() as conn:
            conn.execute('INSERT OR IGNORE INTO attendance_records (date, uid, name, group_id, shift) VALUES (?, ?, ?, ?, ?)', (date_key, uid, name, group_id, shift))

    def upsert_attendance_record(
        self,
        date_key: str,
        uid: str,
        name: str,
        group_id: str,
        shift: str = '',
        in_time: str = '',
        break_start: str = '',
        break_end: str = '',
        out_time: str = '',
        break_min: Any = None,
        work_min: Any = None,
        net_min: Any = None,
        remark: str = '',
        status: str = '未上班打卡',
    ) -> str:
        with connection() as conn:
            existing = conn.execute('SELECT id FROM attendance_records WHERE uid = ? AND date = ?', (uid, date_key)).fetchone()
            if existing:
                conn.execute(
                    '''UPDATE attendance_records
                       SET name=?, group_id=?, shift=?, in_time=?, break_start=?, break_end=?, out_time=?,
                           break_min=?, work_min=?, net_min=?, remark=?, status=?, updated_at=CURRENT_TIMESTAMP
                       WHERE uid=? AND date=?''',
                    (name, group_id, shift, in_time, break_start, break_end, out_time, break_min, work_min, net_min, remark, status, uid, date_key),
                )
                return 'update'
            conn.execute(
                '''INSERT INTO attendance_records (date, uid, name, group_id, shift, in_time, break_start, break_end, out_time, break_min, work_min, net_min, remark, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (date_key, uid, name, group_id, shift, in_time, break_start, break_end, out_time, break_min, work_min, net_min, remark, status),
            )
            return 'insert'

    def add_attendance_event(self, uid: str, group_id: str, work_date: str, action: str, event_time: str) -> None:
        with connection() as conn:
            conn.execute('INSERT INTO attendance_events (uid, group_id, work_date, action, event_time) VALUES (?, ?, ?, ?, ?)', (uid, group_id, work_date, action, event_time))

    def list_all_attendance(self) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute('SELECT * FROM attendance_records ORDER BY date DESC, uid').fetchall()
        return [dict(r) for r in rows]

    def get_latest_attendance_date(self) -> str | None:
        with connection() as conn:
            row = conn.execute('SELECT MAX(date) AS latest FROM attendance_records').fetchone()
        return row['latest'] if row and row['latest'] else None

    def update_attendance_fields(self, uid: str, date_key: str, **fields: Any) -> None:
        if not fields:
            return
        assignments = ', '.join([f'{k} = ?' for k in fields.keys()]) + ', updated_at = CURRENT_TIMESTAMP'
        params = list(fields.values()) + [uid, date_key]
        with connection() as conn:
            conn.execute(f'UPDATE attendance_records SET {assignments} WHERE uid = ? AND date = ?', params)

    def list_signups(self, target_date: str) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute('SELECT id, uid, name, group_id, shift, signup_at, window, status FROM signups WHERE work_date = ? ORDER BY signup_at DESC', (target_date,)).fetchall()
        return [{'id': r['id'], 'uid': r['uid'], 'name': r['name'], 'groupId': r['group_id'], 'shift': r['shift'], 'signupAt': r['signup_at'], 'window': r['window'], 'status': r['status']} for r in rows]

    def list_attendance(self, target_date: str) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute(
                '''SELECT id, date, uid, name, group_id, shift, in_time, break_start, break_end, out_time,
                          break_min, work_min, net_min, remark, status
                   FROM attendance_records WHERE date = ? ORDER BY COALESCE(in_time, ''), uid''',
                (target_date,),
            ).fetchall()
        return [{
            'id': r['id'], 'date': r['date'], 'uid': r['uid'], 'name': r['name'], 'groupId': r['group_id'], 'shift': r['shift'] or '',
            'in': r['in_time'] or '', 'breakStart': r['break_start'] or '', 'breakEnd': r['break_end'] or '', 'out': r['out_time'] or '',
            'breakMin': r['break_min'] if r['break_min'] is not None else '', 'workMin': r['work_min'] if r['work_min'] is not None else '',
            'netMin': r['net_min'] if r['net_min'] is not None else '', 'remark': r['remark'] or '', 'status': r['status'],
        } for r in rows]

    def list_logs(self, limit: int = 30) -> list[dict[str, Any]]:
        with connection() as conn:
            rows = conn.execute('SELECT log_time, level, tag, message FROM system_logs ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [{'time': r['log_time'], 'level': r['level'], 'tag': r['tag'], 'message': r['message']} for r in rows]

    def replace_bonus_rules(self, rules: list[dict[str, Any]]) -> int:
        with connection() as conn:
            conn.execute('DELETE FROM bonus_rules')
            for r in rules:
                conn.execute(
                    '''INSERT INTO bonus_rules (rule_date, source_shift, shift_alias, bonus_per_hour, source_sheet, is_active)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (r.get('rule_date') or '', r.get('source_shift') or '', r.get('shift_alias') or '', r.get('bonus_per_hour'), r.get('source_sheet') or '', 1 if r.get('is_active', True) else 0),
                )
        return len(rules)

    def list_bonus_rules(self, target_date: str | None = None) -> list[dict[str, Any]]:
        sql = 'SELECT id, rule_date, source_shift, shift_alias, bonus_per_hour, source_sheet FROM bonus_rules WHERE is_active = 1'
        params: list[Any] = []
        if target_date:
            sql += ' AND (rule_date = ? OR rule_date = "")'
            params.append(target_date)
        sql += ' ORDER BY COALESCE(rule_date, "") DESC, id DESC'
        with connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def lookup_bonus_per_hour(self, target_date: str, shift_alias: str) -> float | None:
        with connection() as conn:
            row = conn.execute(
                '''SELECT bonus_per_hour FROM bonus_rules
                   WHERE is_active = 1 AND shift_alias = ? AND (rule_date = ? OR rule_date = '')
                   ORDER BY CASE WHEN rule_date = ? THEN 0 ELSE 1 END, id DESC LIMIT 1''',
                (shift_alias, target_date, target_date),
            ).fetchone()
        return float(row['bonus_per_hour']) if row and row['bonus_per_hour'] is not None else None


def upsert_employee(self, uid: str, name: str, group_id: str, role: str = 'staff', status: str = 'active', source: str = '首次互動自動建檔') -> None:
    with connection() as conn:
        conn.execute(
            '''INSERT INTO employees (uid, name, group_id, role, status, source)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(uid) DO UPDATE SET
                 name = CASE WHEN excluded.name != '' THEN excluded.name ELSE employees.name END,
                 group_id = CASE WHEN excluded.group_id != '' THEN excluded.group_id ELSE employees.group_id END,
                 updated_at = CURRENT_TIMESTAMP''',
            (uid, name, group_id, role, status, source),
        )

def update_employee_latest_shift(self, uid: str, latest_shift: str) -> None:
    with connection() as conn:
        conn.execute(
            'UPDATE employees SET latest_shift = ?, updated_at = CURRENT_TIMESTAMP WHERE uid = ?',
            (latest_shift, uid),
        )

def list_employees(self) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            '''SELECT uid, name, group_id, role, status, source, latest_shift, note
               FROM employees
               ORDER BY updated_at DESC, uid'''
        ).fetchall()
    return [dict(r) for r in rows]

def update_employee_role(self, uid: str, role: str) -> None:
    with connection() as conn:
        conn.execute('UPDATE employees SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE uid = ?', (role, uid))

def update_employee_status(self, uid: str, status: str) -> None:
    with connection() as conn:
        conn.execute('UPDATE employees SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE uid = ?', (status, uid))

def update_employee_note(self, uid: str, note: str) -> None:
    with connection() as conn:
        conn.execute('UPDATE employees SET note = ?, updated_at = CURRENT_TIMESTAMP WHERE uid = ?', (note, uid))
