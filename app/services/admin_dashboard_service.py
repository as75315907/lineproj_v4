from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.services.bonus_service import BonusService
from app.services.db_service import DatabaseService


@dataclass
class AdminDashboardService:
    db: DatabaseService
    bonus_service: BonusService

    def get_dashboard_payload(self, target_date: str | None = None) -> Dict[str, Any]:
        tz = ZoneInfo(settings.timezone)
        default_date = datetime.now(tz).strftime('%Y-%m-%d')
        date_value = target_date or self._pick_best_date(default_date)
        signups = self.db.list_signups(date_value)
        attendance = self.db.list_attendance(date_value)
        invoices = self._build_invoices(attendance, date_value)
        bonus_rules = self.bonus_service.get_dashboard_rules(date_value)
        logs = self.db.list_logs(limit=30)
        stats = {
            'signupCount': len(signups),
            'workingCount': len([r for r in attendance if r['status'] in ['上班打卡完成', '休息中', '休息後上工中']]),
            'offDutyCount': len([r for r in attendance if r['status'] == '已下班']),
            'pendingSync': len([r for r in invoices if r['sync'] == '待同步']),
        }
        return {'date': date_value, 'stats': stats, 'signups': signups, 'attendance': attendance, 'invoices': invoices, 'bonusRules': bonus_rules, 'logs': logs}

    def _pick_best_date(self, default_date: str) -> str:
        if self.db.list_signups(default_date) or self.db.list_attendance(default_date):
            return default_date
        latest_signup = self.db.get_latest_signup_date()
        latest_att = self.db.get_latest_attendance_date()
        return max([d for d in [latest_signup, latest_att, default_date] if d])

    def _build_invoices(self, attendance: List[Dict[str, Any]], target_date: str) -> List[Dict[str, Any]]:
        rows = []
        for idx, r in enumerate(attendance, start=1):
            shift = r.get('shift', '') or ''
            wage = 190 if shift == '早班 07:00' else 210 if shift == '晚班 22:00' else 0
            bonus = self.bonus_service.resolve_bonus(target_date, shift)
            net_min = r.get('netMin') or 0
            break_min = r.get('breakMin') or 0
            net_hours = round(net_min / 60, 2) if net_min else 0
            total_hours = net_hours + round(break_min / 60, 2)
            salary = round(wage * net_hours)
            bonus_amount = round(bonus * net_hours)
            sync = '已同步' if r.get('status') == '已下班' else '待同步'
            rows.append({'id': idx, 'uid': r.get('uid'), 'date': r.get('date'), 'shift': shift, 'name': r.get('name'), 'in': r.get('in'), 'out': r.get('out'), 'totalHours': f'{total_hours:.2f}', 'breakStart': r.get('breakStart'), 'breakEnd': r.get('breakEnd'), 'breakHours': f'{(break_min / 60):.2f}', 'netHours': f'{net_hours:.2f}', 'wage': wage, 'bonus': bonus, 'salary': salary, 'bonusAmount': bonus_amount, 'sync': sync})
        return rows
