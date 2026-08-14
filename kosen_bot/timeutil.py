from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def now_jst() -> datetime:
    return datetime.now(JST)


def combine_jst(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock, tzinfo=JST)


def parse_clock(value: str) -> time:
    if not re.fullmatch(r"\d{1,2}:\d{2}", value):
        raise ValueError("時刻は HH:MM 形式で指定してください")
    hour_text, minute_text = value.split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    if hour not in range(24) or minute not in range(60):
        raise ValueError("存在しない時刻です")
    return time(hour, minute)


def parse_user_date(value: str, *, today: date | None = None) -> date:
    base = today or now_jst().date()
    normalized = value.strip().lower()
    if normalized == "today":
        return base
    if normalized == "tomorrow":
        return base + timedelta(days=1)
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        pass

    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})", normalized)
    if not match:
        raise ValueError("日付は YYYY-MM-DD、M/D、today、tomorrow のいずれかで指定してください")
    month, day = map(int, match.groups())
    return date(base.year, month, day)


def format_japanese_date(day: date) -> str:
    weekdays = "月火水木金土日"
    return f"{day.year}年{day.month}月{day.day}日（{weekdays[day.weekday()]}）"
