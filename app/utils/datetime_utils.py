from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings


def now_taipei() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


def date_key(dt: datetime) -> str:
    return dt.astimezone(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d")


def time_str(dt: datetime) -> str:
    return dt.astimezone(ZoneInfo(settings.timezone)).strftime("%H:%M:%S")


def get_signup_window() -> dict:
    now = now_taipei()
    if settings.test_mode:
        return {
            "ok": True,
            "start": now - timedelta(hours=12),
            "end": now + timedelta(hours=12),
            "message": "TEST_MODE",
        }

    start = now.replace(hour=settings.signup_start_hour, minute=0, second=0, microsecond=0)
    end = (start + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    if now < start:
        return {"ok": False, "message": "⏳ 報名尚未開始。\n報名時間：21:00 - 00:00"}
    if now >= end:
        return {"ok": False, "message": "⌛ 報名已截止。\n報名時間：21:00 - 00:00"}

    return {"ok": True, "start": start, "end": end, "message": "OK"}
