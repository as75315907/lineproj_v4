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

    def get_dashboard_payload(
        self,
        signup_date: str | None = None,
        attendance_date: str | None = None,
    ) -> Dict[str, Any]:
        tz = ZoneInfo(settings.timezone)
        today = datetime.now(tz).strftime('%Y-%m-%d')
        latest_signup = self.db.get_latest_signup_date()
        latest_att = self.db.get_latest_attendance_date()
        resolved_signup_date = signup_date or self._pick_signup_date(today, latest_signup)
        resolved_attendance_date = attendance_date or self._pick_attendance_date(today, latest_att)
        signups = self.db.list_signups(resolved_signup_date)
        attendance = self.db.list_attendance(resolved_attendance_date)
        latest_signup_date = latest_signup or resolved_signup_date
        latest_signup_signups = self.db.list_signups(latest_signup_date) if latest_signup_date else signups
        invoices = self._build_invoices(attendance, resolved_attendance_date)
        bonus_rules = self.bonus_service.get_dashboard_rules(resolved_attendance_date)
        logs = self.db.list_logs(limit=30)
        overview = self._build_overview(today, latest_signup, latest_att)
        signup_date_context = self._build_date_context(
            today=today,
            selected_date=resolved_signup_date,
            latest_date=latest_signup,
            mode='signup',
        )
        attendance_date_context = self._build_date_context(
            today=today,
            selected_date=resolved_attendance_date,
            latest_date=latest_att,
            mode='attendance',
        )
        stats = {
            'signupCount': len(latest_signup_signups),
            'signupSelectedCount': len(signups),
            'signupLatestDate': latest_signup_date,
            'workingCount': len([r for r in attendance if r['status'] in ['上班打卡完成', '未報班直接上班', '休息中', '休息後上工中']]),
            'offDutyCount': len([r for r in attendance if r['status'] == '已下班']),
            'pendingSync': len([r for r in invoices if r['sync'] == '待同步']),
        }
        return {
            'date': resolved_attendance_date,
            'signupDate': resolved_signup_date,
            'attendanceDate': resolved_attendance_date,
            'stats': stats,
            'signups': signups,
            'attendance': attendance,
            'invoices': invoices,
            'bonusRules': bonus_rules,
            'logs': logs,
            'overview': overview,
            'signupDateContext': signup_date_context,
            'attendanceDateContext': attendance_date_context,
        }

    def _pick_signup_date(self, today: str, latest_signup: str | None) -> str:
        if latest_signup and latest_signup >= today:
            return latest_signup
        return today

    def _pick_attendance_date(self, today: str, latest_att: str | None) -> str:
        if self.db.list_attendance(today):
            return today
        return latest_att or today

    def _build_date_context(
        self,
        today: str,
        selected_date: str,
        latest_date: str | None,
        mode: str,
    ) -> Dict[str, Any]:
        candidates: list[tuple[str, str]] = [
            ('today', today),
        ]
        if latest_date:
            candidates.append(('latest', latest_date))

        counts_cache: dict[str, dict[str, int]] = {}

        def get_counts(target_date: str) -> dict[str, int]:
            if target_date not in counts_cache:
                signup_count = len(self.db.list_signups(target_date))
                attendance_count = len(self.db.list_attendance(target_date))
                counts_cache[target_date] = {
                    'signupCount': signup_count,
                    'attendanceCount': attendance_count,
                    'primaryCount': signup_count if mode == 'signup' else attendance_count,
                }
            return counts_cache[target_date]

        merged: dict[str, dict[str, Any]] = {}
        for source, target_date in candidates:
            if target_date not in merged:
                merged[target_date] = {
                    'date': target_date,
                    'label': '今天',
                    **get_counts(target_date),
                }
            if source == 'today':
                merged[target_date]['label'] = '今天'
            elif source == 'latest':
                latest_label = '最新報班' if mode == 'signup' else '最新打卡'
                if merged[target_date]['label'] == '今天':
                    merged[target_date]['label'] = f'今天 / {latest_label}'
                else:
                    merged[target_date]['label'] = latest_label

        options = sorted(merged.values(), key=lambda item: item['date'], reverse=True)
        if mode == 'signup':
            if latest_date and latest_date > today:
                if selected_date == latest_date:
                    hint = f'報班區已自動切到 {latest_date}，避免漏看隔天班表。'
                else:
                    hint = f'最新報班資料在 {latest_date}，可切到「最新報班」。'
            elif selected_date == today:
                hint = '報班區目前顯示今天。晚間若有人先報明天班，這裡會帶到最新報班日。'
            else:
                hint = f'報班區目前顯示 {selected_date}。'
        else:
            if selected_date == today:
                hint = '出勤區目前顯示今天打卡。'
            else:
                hint = f'出勤區目前顯示 {selected_date} 的資料。'

        return {
            'today': today,
            'selected': selected_date,
            'latestDate': latest_date or '',
            'hint': hint,
            'options': options,
            'mode': mode,
        }

    def _build_overview(self, today: str, latest_signup: str | None, latest_att: str | None) -> Dict[str, Any]:
        today_signups = self.db.list_signups(today)
        today_attendance = self.db.list_attendance(today)
        today_attendance_uids = {row.get('uid', '') for row in today_attendance if row.get('uid')}
        missing_checkins = [row for row in today_signups if row.get('uid') not in today_attendance_uids]
        next_signup_date = latest_signup if latest_signup and latest_signup >= today else today
        next_signup_count = len(self.db.list_signups(next_signup_date))
        today_working_count = len([row for row in today_attendance if row.get('status') in ['上班打卡完成', '未報班直接上班', '休息中', '休息後上工中', '已下班']])
        latest_signup_label = latest_signup or today
        latest_att_label = latest_att or today
        return {
            'missingCheckins': {
                'count': len(missing_checkins),
                'date': today,
                'names': [row.get('name', '') for row in missing_checkins[:8]],
            },
            'missingShiftAssignments': {
                'count': len([row for row in today_attendance if row.get('status') == '未報班直接上班']),
                'date': today,
                'names': [row.get('name', '') for row in today_attendance if row.get('status') == '未報班直接上班'][:8],
            },
            'nextSignup': {
                'date': next_signup_date,
                'count': next_signup_count,
            },
            'latestVsToday': {
                'latestSignupDate': latest_signup_label,
                'todayAttendanceDate': today,
                'todayAttendanceCount': today_working_count,
                'latestAttendanceDate': latest_att_label,
            },
        }

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
