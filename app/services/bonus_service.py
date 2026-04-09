from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.db_service import DatabaseService
from app.services.sheets_service import GoogleSheetsService
from app.utils.sheet_parsers import normalize_header_map, parse_datetime_like


@dataclass
class BonusService:
    sheets: GoogleSheetsService
    db: DatabaseService

    def import_bonus_rules(self) -> int:
        values = self.sheets.get_all_values(settings.bonus_sheet_name)
        if not values or len(values) <= 1:
            return 0
        header_map = normalize_header_map(values[0])
        date_idx = header_map.get('日期', header_map.get('生效日期', -1))
        shift_idx = header_map.get('班別', header_map.get('來源班別', -1))
        alias_idx = header_map.get('對應班別別名', header_map.get('班別別名', header_map.get('別名', -1)))
        bonus_idx = header_map.get('獎金(每小時)', header_map.get('獎金', header_map.get('獎金/時', -1)))
        rules: list[dict[str, Any]] = []
        for row in values[1:]:
            source_shift = row[shift_idx].strip() if shift_idx >= 0 and len(row) > shift_idx else ''
            if not source_shift:
                continue
            raw_date = row[date_idx].strip() if date_idx >= 0 and len(row) > date_idx else ''
            dt = parse_datetime_like(raw_date) if raw_date else None
            alias = row[alias_idx].strip() if alias_idx >= 0 and len(row) > alias_idx else settings.shift_alias_map.get(source_shift, '')
            raw_bonus = row[bonus_idx].strip() if bonus_idx >= 0 and len(row) > bonus_idx else ''
            try:
                bonus = float(raw_bonus) if raw_bonus != '' else None
            except ValueError:
                bonus = None
            rules.append({
                'rule_date': dt.strftime('%Y-%m-%d') if dt else '',
                'source_shift': source_shift,
                'shift_alias': alias,
                'bonus_per_hour': bonus,
                'source_sheet': settings.bonus_sheet_name,
                'is_active': True,
            })
        return self.db.replace_bonus_rules(rules)

    def get_dashboard_rules(self, target_date: str) -> list[dict[str, Any]]:
        rows = self.db.list_bonus_rules(target_date)
        result = []
        for idx, row in enumerate(rows, start=1):
            result.append({
                'id': idx,
                'date': row.get('rule_date') or '',
                'sourceShift': row.get('source_shift') or '',
                'alias': row.get('shift_alias') or '',
                'bonusPerHour': row.get('bonus_per_hour') if row.get('bonus_per_hour') is not None else '',
                'sourceSheet': row.get('source_sheet') or settings.bonus_sheet_name,
                'status': '已對應' if row.get('shift_alias') else '待補別名',
            })
        return result

    def resolve_bonus(self, target_date: str, shift_name: str) -> float:
        alias = settings.shift_alias_map.get(shift_name, '')
        value = self.db.lookup_bonus_per_hour(target_date, alias) if alias else None
        if value is not None:
            return value
        if alias == '早班':
            return 15
        if alias == '大夜班':
            return 20
        return 0.0
