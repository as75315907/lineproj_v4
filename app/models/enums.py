from enum import Enum


class AttendanceAction(str, Enum):
    IN = "IN"
    BREAK_START = "BREAK_START"
    BREAK_END = "BREAK_END"
    OUT = "OUT"
