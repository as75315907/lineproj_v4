from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums import AttendanceAction


class AttendanceResult(BaseModel):
    ok: bool
    message: str


class AttendanceContext(BaseModel):
    uid: str
    name: str
    group_id: str = ""
    action: AttendanceAction
    event_time: datetime


class AttendanceRow(BaseModel):
    date_key: str
    uid: str
    name: str
    group_id: str
    in_time: Optional[str] = None
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    out_time: Optional[str] = None
