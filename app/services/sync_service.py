from __future__ import annotations

from dataclasses import dataclass

from app.services.attendance_service import AttendanceService
from app.services.bonus_service import BonusService
from app.services.db_service import DatabaseService
from app.services.sheets_service import GoogleSheetsService
from app.services.signup_service import SignupService


@dataclass
class SyncService:
    db: DatabaseService
    sheets: GoogleSheetsService
    signup_service: SignupService
    attendance_service: AttendanceService
    bonus_service: BonusService

    def import_all(self) -> dict:
        if not self.sheets.is_available():
            return {'ok': False, 'message': 'Google Sheets 尚未設定完成', 'details': {}}
        signup_count = self.signup_service.import_signup_sheet()
        attendance_count = self.attendance_service.import_attendance_sheet()
        bonus_count = self.bonus_service.import_bonus_rules()
        self.db.add_log('INFO', 'sheet.import', f'signup={signup_count} attendance={attendance_count} bonus={bonus_count}')
        return {'ok': True, 'message': '已將 Google Sheet 匯入 SQLite', 'details': {'signup': signup_count, 'attendance': attendance_count, 'bonus': bonus_count}}
