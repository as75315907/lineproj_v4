from __future__ import annotations

from datetime import timedelta

from app.core.config import settings
from app.core.logging import get_logger
from app.services.db_service import DatabaseService
from app.services.sheets_service import GoogleSheetsService
from app.utils.datetime_utils import get_signup_window, now_taipei
from app.utils.sheet_parsers import (
    normalize_header_map,
    parse_datetime_like,
    signup_datetime_to_work_date,
)

logger = get_logger(__name__)


class SignupService:
    HEADER = ['UID', '姓名', '班別', '登記時間']

    def __init__(self, sheets_service: GoogleSheetsService, db_service: DatabaseService) -> None:
        self.sheets = sheets_service
        self.db = db_service

    def ensure_sheet_ready(self) -> None:
        """
        只有在真的需要操作 Google Sheet 時才呼叫，
        避免 webhook verify / 冷啟動時一進來就碰外部服務。
        """
        self.sheets.ensure_header(settings.signup_sheet_name, self.HEADER)

    @staticmethod
    def format_shift(raw_shift: str) -> str:
        if raw_shift == 'shift=早7':
            return '早班 07:00'
        if raw_shift == 'shift=晚10':
            return '晚班 22:00'
        return raw_shift

    def sync_signup_to_sheet(self, uid: str, name: str, shift_text: str, now_text: str) -> None:
        if settings.realtime_sheet_sync:
            self.ensure_sheet_ready()
            self.sheets.append_row(settings.signup_sheet_name, [uid, name, shift_text, now_text])

    def upsert_signup(self, uid: str, name: str, group_id: str, raw_shift: str) -> dict:
        window = get_signup_window()
        if not window.get('ok'):
            return {'ok': False, 'message': window['message']}

        shift_text = self.format_shift(raw_shift)
        now_dt = now_taipei()
        now_text = now_dt.strftime('%Y-%m-%d %H:%M:%S')
        work_date = (now_dt + timedelta(days=1)).strftime('%Y-%m-%d')

        action = self.db.upsert_signup(
            uid=uid,
            name=name,
            group_id=group_id,
            shift=shift_text,
            signup_at=now_text,
            window='21:00 - 00:00',
            work_date=work_date,
        )

        logger.info('signup %s uid=%s name=%s shift=%s', action, uid, name, shift_text)
        self.db.add_log(
            'INFO',
            'upsertSignup',
            f'UID={uid} / 姓名={name} / 班別={shift_text} / action={action}',
        )

        # 只有在開啟即時同步時才碰 Google Sheet
        self.sync_signup_to_sheet(uid, name, shift_text, now_text)

        prefix = '🧪【測試模式】' if settings.test_mode else ''
        text = f"{prefix}{'✅ 已登記：' if action == 'insert' else '🔁 已更新：'}{shift_text}"

        return {'ok': True, 'message': text, 'shift_text': shift_text}

    def get_shift_for_work_date(self, uid: str, date_key: str) -> str:
        return self.db.get_shift_for_date(uid, date_key)

    def replace_signup_sheet(self, target_date: str | None = None) -> int:
        self.ensure_sheet_ready()

        rows = self.db.list_all_signups()
        if target_date:
            rows = [r for r in rows if r['work_date'] == target_date]

        sheet_rows = [[r['uid'], r['name'], r['shift'], r['signup_at']] for r in rows]
        self.sheets.replace_sheet_data(settings.signup_sheet_name, [self.HEADER, *sheet_rows])
        return len(sheet_rows)

    def import_signup_sheet(self) -> int:
        self.ensure_sheet_ready()

        values = self.sheets.get_all_values(settings.signup_sheet_name)
        if not values or len(values) <= 1:
            return 0

        header_map = normalize_header_map(values[0])

        uid_idx = header_map.get('UID', 0)
        name_idx = header_map.get('姓名', 1)
        shift_idx = header_map.get('班別', 2)
        signup_idx = header_map.get('登記時間', header_map.get('表後登記時間', 3))

        count = 0

        for row in values[1:]:
            uid = row[uid_idx].strip() if len(row) > uid_idx else ''
            name = row[name_idx].strip() if len(row) > name_idx else ''
            shift = row[shift_idx].strip() if len(row) > shift_idx else ''
            signup_raw = row[signup_idx].strip() if len(row) > signup_idx else ''

            if not uid:
                continue

            signup_dt = parse_datetime_like(signup_raw)
            signup_at = signup_dt.strftime('%Y-%m-%d %H:%M:%S') if signup_dt else signup_raw
            work_date = signup_datetime_to_work_date(signup_dt or signup_raw)

            if not work_date:
                fallback_now = now_taipei()
                work_date = (fallback_now + timedelta(days=1)).strftime('%Y-%m-%d')
                signup_at = signup_at or fallback_now.strftime('%Y-%m-%d %H:%M:%S')

            result = self.db.import_signup(
                uid=uid,
                name=name or f'使用者-{uid[:6]}',
                shift=shift,
                signup_at=signup_at or f'{work_date} 00:00:00',
                work_date=work_date,
            )

            if result != 'skip':
                count += 1

        self.db.add_log('INFO', 'importSignupSheet', f'已從 {settings.signup_sheet_name} 匯入 {count} 筆報班資料')
        logger.info('import signup sheet done count=%s', count)

        return count