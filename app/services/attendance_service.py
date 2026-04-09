from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import AttendanceAction
from app.schemas.attendance import AttendanceContext, AttendanceResult
from app.services.db_service import DatabaseService
from app.services.invoice_service import InvoiceService
from app.services.sheets_service import GoogleSheetsService
from app.utils.datetime_utils import date_key, time_str
from app.utils.sheet_parsers import normalize_header_map, parse_date_key, parse_int_or_none, parse_time_text

logger = get_logger(__name__)


@dataclass
class _RowState:
    in_time: str = ''
    break_start: str = ''
    break_end: str = ''
    out_time: str = ''


def _parse_sec(t: str) -> int | None:
    if not t:
        return None
    h, m, s = [int(x) for x in t.split(':')]
    return h * 3600 + m * 60 + s


class AttendanceService:
    HEADER = ['日期', 'UID', '姓名', '群組ID', '上班時間', '休息開始', '休息結束', '下班時間', '休息分鐘', '工作分鐘', '淨工作分鐘', '備註']

    def __init__(self, sheets_service: GoogleSheetsService, invoice_service: InvoiceService, db_service: DatabaseService) -> None:
        self.sheets = sheets_service
        self.invoice_service = invoice_service
        self.db = db_service
        self.sheets.ensure_header(settings.att_sheet_name, self.HEADER)

    def sync_attendance_to_sheet(self, uid: str, date_key: str, row: dict[str, Any]) -> None:
        if not settings.realtime_sheet_sync:
            return
        values = [date_key, uid, row.get('name', ''), row.get('group_id', ''), row.get('in_time', ''), row.get('break_start', ''), row.get('break_end', ''), row.get('out_time', ''), row.get('break_min', ''), row.get('work_min', ''), row.get('net_min', ''), row.get('remark', '')]
        self.sheets.upsert_row_by_two_keys(settings.att_sheet_name, 1, date_key, 2, uid, values)

    def handle_attendance(self, ctx: AttendanceContext) -> AttendanceResult:
        logger.info('handle attendance uid=%s action=%s', ctx.uid, ctx.action)
        current_date_key = date_key(ctx.event_time)
        current_time_str = time_str(ctx.event_time)
        shift = self.db.get_shift_for_date(ctx.uid, current_date_key)
        self.db.create_attendance_record(current_date_key, ctx.uid, ctx.name, ctx.group_id, shift)
        record = self.db.get_attendance_record(ctx.uid, current_date_key) or {}
        state = _RowState(in_time=record.get('in_time', '') or '', break_start=record.get('break_start', '') or '', break_end=record.get('break_end', '') or '', out_time=record.get('out_time', '') or '')
        duplicate_msg = self._duplicate_message(ctx.name, state, ctx.action)
        if duplicate_msg:
            return AttendanceResult(ok=True, message=duplicate_msg)
        valid, hint = self._is_valid_next(state, ctx.action)
        if not valid:
            return AttendanceResult(ok=False, message=f'⚠️ {ctx.name} 打卡順序不正確。\n{hint}')

        fields: dict[str, Any] = {}
        if ctx.action == AttendanceAction.IN:
            fields.update({'name': ctx.name, 'group_id': ctx.group_id, 'shift': shift, 'in_time': current_time_str, 'break_start': '', 'break_end': '', 'out_time': '', 'remark': '', 'status': '上班打卡完成'})
        elif ctx.action == AttendanceAction.BREAK_START:
            fields.update({'break_start': current_time_str, 'status': '休息中'})
        elif ctx.action == AttendanceAction.BREAK_END:
            fields.update({'break_end': current_time_str, 'status': '休息後上工中'})
        elif ctx.action == AttendanceAction.OUT:
            fields.update({'out_time': current_time_str, 'status': '已下班'})

        merged = {'in_time': fields.get('in_time', state.in_time), 'break_start': fields.get('break_start', state.break_start), 'break_end': fields.get('break_end', state.break_end), 'out_time': fields.get('out_time', state.out_time)}
        break_min, work_min, net_min = self._compute_minutes(merged)
        fields.update({'break_min': break_min, 'work_min': work_min, 'net_min': net_min})

        self.db.update_attendance_fields(ctx.uid, current_date_key, **fields)
        self.db.add_attendance_event(ctx.uid, ctx.group_id, current_date_key, ctx.action.value, f'{current_date_key} {current_time_str}')
        self.db.add_log('INFO', 'attendance', f'UID={ctx.uid} / action={ctx.action.value} / {self._label(ctx.action)}完成')

        updated = self.db.get_attendance_record(ctx.uid, current_date_key) or {}
        self.sync_attendance_to_sheet(ctx.uid, current_date_key, updated)
        self.invoice_service.sync_attendance_to_invoice(uid=ctx.uid, name=ctx.name, date_key=current_date_key, shift=shift, in_time=updated.get('in_time', '') or '', out_time=updated.get('out_time', '') or '', break_start=updated.get('break_start', '') or '', break_end=updated.get('break_end', '') or '', break_min=updated.get('break_min'), net_min=updated.get('net_min'))
        return AttendanceResult(ok=True, message=f'✅ {ctx.name} 已完成【{self._label(ctx.action)}】： {current_time_str}')

    def replace_attendance_sheet(self, target_date: str | None = None) -> int:
        rows = self.db.list_all_attendance()
        if target_date:
            rows = [r for r in rows if r['date'] == target_date]
        sheet_rows = [[r['date'], r['uid'], r['name'], r['group_id'], r['in_time'], r['break_start'], r['break_end'], r['out_time'], r['break_min'] if r['break_min'] is not None else '', r['work_min'] if r['work_min'] is not None else '', r['net_min'] if r['net_min'] is not None else '', r['remark']] for r in rows]
        self.sheets.replace_sheet_data(settings.att_sheet_name, [self.HEADER, *sheet_rows])
        return len(sheet_rows)

    def import_attendance_sheet(self) -> int:
        values = self.sheets.get_all_values(settings.att_sheet_name)
        if not values or len(values) <= 1:
            return 0
        header_map = normalize_header_map(values[0])
        count = 0
        for row in values[1:]:
            date_value = row[header_map.get('日期', 0)].strip() if len(row) > header_map.get('日期', 0) else ''
            uid = row[header_map.get('UID', 1)].strip() if len(row) > header_map.get('UID', 1) else ''
            if not uid or not date_value:
                continue
            name = row[header_map.get('姓名', 2)].strip() if len(row) > header_map.get('姓名', 2) else ''
            group_id = row[header_map.get('群組ID', 3)].strip() if len(row) > header_map.get('群組ID', 3) else ''
            in_time = parse_time_text(row[header_map.get('上班時間', 4)]) if len(row) > header_map.get('上班時間', 4) else ''
            break_start = parse_time_text(row[header_map.get('休息開始', 5)]) if len(row) > header_map.get('休息開始', 5) else ''
            break_end = parse_time_text(row[header_map.get('休息結束', 6)]) if len(row) > header_map.get('休息結束', 6) else ''
            out_time = parse_time_text(row[header_map.get('下班時間', 7)]) if len(row) > header_map.get('下班時間', 7) else ''
            break_min = parse_int_or_none(row[header_map.get('休息分鐘', 8)]) if len(row) > header_map.get('休息分鐘', 8) else None
            work_min = parse_int_or_none(row[header_map.get('工作分鐘', 9)]) if len(row) > header_map.get('工作分鐘', 9) else None
            net_min = parse_int_or_none(row[header_map.get('淨工作分鐘', 10)]) if len(row) > header_map.get('淨工作分鐘', 10) else None
            remark = row[header_map.get('備註', 11)].strip() if len(row) > header_map.get('備註', 11) else ''
            date_key_value = parse_date_key(date_value)
            shift = self.db.get_shift_for_date(uid, date_key_value)
            status = self._status_from_times(in_time, break_start, break_end, out_time)
            result = self.db.upsert_attendance_record(date_key=date_key_value, uid=uid, name=name or f'使用者-{uid[:6]}', group_id=group_id, shift=shift, in_time=in_time, break_start=break_start, break_end=break_end, out_time=out_time, break_min=break_min, work_min=work_min, net_min=net_min, remark=remark, status=status)
            if result != 'skip':
                count += 1
        return count

    def _compute_minutes(self, merged: dict[str, str]) -> tuple[int | None, int | None, int | None]:
        in_s = _parse_sec(merged.get('in_time', ''))
        bs_s = _parse_sec(merged.get('break_start', ''))
        be_s = _parse_sec(merged.get('break_end', ''))
        out_s = _parse_sec(merged.get('out_time', ''))
        break_min = None
        work_min = None
        net_min = None
        if bs_s is not None and be_s is not None and be_s >= bs_s:
            break_min = round((be_s - bs_s) / 60)
        if in_s is not None and out_s is not None and out_s >= in_s:
            work_min = round((out_s - in_s) / 60)
            net_min = work_min - (break_min or 0)
            if net_min < 0:
                net_min = 0
        return break_min, work_min, net_min

    def _duplicate_message(self, name: str, state: _RowState, action: AttendanceAction) -> str | None:
        if action == AttendanceAction.IN and state.in_time and not state.out_time:
            return f'ℹ️ 你已經打過【上班打卡】： {state.in_time}'
        if action == AttendanceAction.BREAK_START and state.break_start:
            return f'ℹ️ 你已經打過【休息開始打卡】： {state.break_start}'
        if action == AttendanceAction.BREAK_END and state.break_end:
            return f'ℹ️ 你已經打過【休息結束打卡】： {state.break_end}'
        if action == AttendanceAction.OUT and state.out_time:
            return f'ℹ️ 你已經打過【下班打卡】： {state.out_time}'
        return None

    def _is_valid_next(self, state: _RowState, action: AttendanceAction) -> tuple[bool, str]:
        has_in = bool(state.in_time)
        has_bs = bool(state.break_start)
        has_be = bool(state.break_end)
        has_out = bool(state.out_time)
        if action == AttendanceAction.IN:
            return (not has_in or has_out), ''
        if not has_in:
            return False, '請先點「✅ 上班打卡」'
        if has_out:
            return False, '你今天已經下班了'
        if action == AttendanceAction.BREAK_START:
            return (not has_bs or (has_bs and has_be)), ''
        if action == AttendanceAction.BREAK_END:
            return (has_bs and not has_be), '請先點「🍱 休息開始」'
        if action == AttendanceAction.OUT:
            if has_bs and not has_be:
                return False, '你目前在休息中，請先點「⏱️ 休息結束」'
            return True, ''
        return True, ''

    def _label(self, action: AttendanceAction) -> str:
        return {
            AttendanceAction.IN: '上班打卡',
            AttendanceAction.BREAK_START: '休息開始打卡',
            AttendanceAction.BREAK_END: '休息結束打卡',
            AttendanceAction.OUT: '下班打卡',
        }[action]

    def _status_from_times(self, in_time: str, break_start: str, break_end: str, out_time: str) -> str:
        if out_time:
            return '已下班'
        if break_start and not break_end:
            return '休息中'
        if break_start and break_end:
            return '休息後上工中'
        if in_time:
            return '上班打卡完成'
        return '未上班打卡'
