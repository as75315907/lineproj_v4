from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.services.bonus_service import BonusService
from app.services.sheets_service import GoogleSheetsService

logger = get_logger(__name__)


@dataclass
class InvoiceService:
    sheets: GoogleSheetsService
    bonus_service: BonusService

    HEADER = [
        'UID', '日期', '班別', '姓名', '上班時間', '下班時間', '出勤總時數', '休息開始', '休息結束',
        '休息時間', '實際出勤總時數', '時薪', '獎金(每小時)', '薪資', '獎金總額', '同步狀態',
    ]

    def __post_init__(self) -> None:
        self.sheets.ensure_header(settings.invoice_sheet_name, self.HEADER)

    def _money_fields(self, date_key: str, shift: str, break_min: int | None, net_min: int | None) -> tuple[str, str, float, int, float, int, int]:
        wage = 190 if shift == '早班 07:00' else 210 if shift == '晚班 22:00' else 0
        bonus = self.bonus_service.resolve_bonus(date_key, shift)
        break_hours = ((break_min or 0) / 60)
        net_hours = ((net_min or 0) / 60)
        total_hours = net_hours + break_hours
        salary = round(wage * net_hours)
        bonus_amount = round(bonus * net_hours)
        return f'{total_hours:.2f}', f'{break_hours:.2f}', round(net_hours, 2), wage, bonus, salary, bonus_amount

    def build_invoice_row(
        self,
        uid: str,
        name: str,
        date_key: str,
        shift: str,
        in_time: str,
        out_time: str,
        break_start: str,
        break_end: str,
        break_min: int | None = None,
        net_min: int | None = None,
        sync_status: str = '已同步',
    ) -> list[str | int | float]:
        total_hours, break_hours, net_hours, wage, bonus, salary, bonus_amount = self._money_fields(date_key, shift, break_min, net_min)
        return [uid, date_key, shift, name, in_time, out_time, total_hours, break_start, break_end, break_hours, f'{net_hours:.2f}', wage, bonus, salary, bonus_amount, sync_status]

    def sync_attendance_to_invoice(self, uid: str, name: str, date_key: str, shift: str, in_time: str, out_time: str, break_start: str, break_end: str, break_min: int | None = None, net_min: int | None = None) -> None:
        if not settings.realtime_sheet_sync:
            return
        row = self.build_invoice_row(uid, name, date_key, shift, in_time, out_time, break_start, break_end, break_min, net_min, sync_status='已同步' if out_time else '待同步')
        mode = self.sheets.upsert_row_by_two_keys(settings.invoice_sheet_name, 1, uid, 2, date_key, row)
        logger.info('invoice sheet %s uid=%s date=%s', mode, uid, date_key)

    def replace_invoice_sheet(self, rows: list[list[str | int | float]]) -> None:
        self.sheets.replace_sheet_data(settings.invoice_sheet_name, [self.HEADER, *rows])
