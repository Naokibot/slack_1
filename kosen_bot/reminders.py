from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .db import Database, Reminder
from .timeutil import JST, combine_jst, now_jst, parse_clock, parse_user_date


@dataclass(frozen=True)
class ReminderInput:
    title: str
    day: date
    clock: time

    @property
    def scheduled_at(self) -> datetime:
        return combine_jst(self.day, self.clock)


def validate_title(title: str) -> str:
    cleaned = " ".join(title.strip().split())
    if not cleaned:
        raise ValueError("予定を入力してください")
    if len(cleaned) > 300:
        raise ValueError("予定は300文字以内で入力してください")
    return cleaned


def parse_add_command(text: str, *, today: date | None = None) -> ReminderInput:
    parts = text.strip().split(maxsplit=3)
    if len(parts) < 4 or parts[0].lower() != "add":
        raise ValueError("例：/reminder add 2026-08-20 19:00 数学の過去問")
    day = parse_user_date(parts[1], today=today)
    clock = parse_clock(parts[2])
    title = validate_title(parts[3])
    return ReminderInput(title=title, day=day, clock=clock)


def format_reminder(reminder: Reminder, *, include_id: bool = True) -> str:
    when = reminder.scheduled_at.astimezone(JST)
    prefix = f"#{reminder.id}\n" if include_id else ""
    return f"{prefix}{reminder.title}\n{when.month}月{when.day}日 {when:%H:%M}"


class ReminderService:
    def __init__(self, db: Database):
        self.db = db

    def create(self, item: ReminderInput, channel_id: str, user_id: str, now: datetime | None = None) -> int:
        current = now or now_jst()
        if item.scheduled_at <= current:
            raise ValueError("未来の日時を指定してください")
        return self.db.add_reminder(item.title, item.scheduled_at, channel_id, user_id, current)

    def list_all(self, now: datetime | None = None) -> list[Reminder]:
        current = now or now_jst()
        return self.db.list_reminders(start=current)

    def list_for_day(self, day: date) -> list[Reminder]:
        start = datetime.combine(day, time.min, tzinfo=JST)
        end = start + timedelta(days=1)
        return self.db.list_reminders(start=start, end=end)

    def due(self, now: datetime | None = None, late_window_minutes: int = 30) -> list[Reminder]:
        current = now or now_jst()
        earliest = current - timedelta(minutes=late_window_minutes)
        return self.db.due_reminders(earliest, current)

    def expire_stale(self, now: datetime | None = None, late_window_minutes: int = 30) -> int:
        current = now or now_jst()
        return self.db.expire_old_reminders(current - timedelta(minutes=late_window_minutes))
