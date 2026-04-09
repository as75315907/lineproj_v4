from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.db_service import DatabaseService


ROLE_LABELS = {
    'staff': '一般員工',
    'supervisor': '主管',
    'leader': '幹部',
    'admin': '管理員',
}

STATUS_LABELS = {
    'active': '啟用中',
    'inactive': '停用',
}


@dataclass
class EmployeeService:
    db: DatabaseService

    def ensure_employee(self, uid: str, name: str = '', group_id: str = '') -> None:
        if not uid:
            return
        self.db.upsert_employee(uid=uid, name=name or f'使用者-{uid[:6]}', group_id=group_id or '')

    def list_employees(self) -> list[dict[str, Any]]:
        rows = self.db.list_employees()
        result: list[dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            result.append({
                'id': idx,
                'uid': row.get('uid', ''),
                'name': row.get('name', ''),
                'groupId': row.get('group_id', ''),
                'role': ROLE_LABELS.get(row.get('role', 'staff'), '一般員工'),
                'roleCode': row.get('role', 'staff'),
                'status': STATUS_LABELS.get(row.get('status', 'active'), '啟用中'),
                'statusCode': row.get('status', 'active'),
                'latestShift': row.get('latest_shift', ''),
                'source': row.get('source', '首次互動自動建檔'),
                'note': row.get('note', ''),
            })
        return result

    def update_role(self, uid: str, role: str) -> None:
        self.db.update_employee_role(uid, role)

    def update_status(self, uid: str, status: str) -> None:
        self.db.update_employee_status(uid, status)

    def update_note(self, uid: str, note: str) -> None:
        self.db.update_employee_note(uid, note)
