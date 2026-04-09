from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

CHINESE_AMPM = {
    '上午': 'AM',
    '下午': 'PM',
}


def _clean_text(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()


def parse_datetime_like(value: Any) -> datetime | None:
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    text = _clean_text(value)
    if not text:
        return None
    for zh, en in CHINESE_AMPM.items():
        text = text.replace(zh, en)
    text = text.replace('\u202f', ' ').replace('  ', ' ')

    fmts = [
        '%Y/%m/%d %p %I:%M:%S',
        '%Y/%m/%d %p %I:%M',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y/%m/%d',
        '%Y-%m-%d',
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_date_key(value: Any) -> str:
    dt = parse_datetime_like(value)
    if dt:
        return dt.strftime('%Y-%m-%d')
    text = _clean_text(value).replace('/', '-')
    return text


def parse_time_text(value: Any) -> str:
    dt = parse_datetime_like(value)
    if dt:
        return dt.strftime('%H:%M:%S')

    text = _clean_text(value)
    if not text:
        return ''
    for zh, en in CHINESE_AMPM.items():
        text = text.replace(zh, en)
    fmts = ['%H:%M:%S', '%H:%M', '%p %I:%M:%S', '%p %I:%M']
    for fmt in fmts:
        try:
            return datetime.strptime(text, fmt).strftime('%H:%M:%S')
        except ValueError:
            continue
    return text


def parse_int_or_none(value: Any) -> int | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def signup_datetime_to_work_date(signup_at: Any) -> str:
    dt = parse_datetime_like(signup_at)
    if not dt:
        return ''
    return (dt + timedelta(days=1)).strftime('%Y-%m-%d')


def normalize_header_map(header_row: list[Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        key = _clean_text(cell)
        if key:
            result[key] = idx
    return result
