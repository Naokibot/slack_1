from __future__ import annotations

from datetime import date, datetime, time

from .db import Database
from .timeutil import format_japanese_date, now_jst, parse_clock


class CountdownService:
    def __init__(self, db: Database, default_exam_date: date, default_notify_time: time):
        self.db = db
        self.default_exam_date = default_exam_date
        self.default_notify_time = default_notify_time

    def exam_date(self) -> date:
        value = self.db.get_setting("exam_date")
        if value is None:
            return self.default_exam_date
        try:
            return date.fromisoformat(value)
        except ValueError:
            return self.default_exam_date

    def notify_time(self) -> time:
        value = self.db.get_setting("countdown_notify_time")
        if value is None:
            return self.default_notify_time
        try:
            return parse_clock(value)
        except ValueError:
            return self.default_notify_time

    def set_exam_date(self, exam_date: date, now: datetime | None = None) -> None:
        self.db.set_setting("exam_date", exam_date.isoformat(), now or now_jst())
        self.db.set_setting("countdown_last_sent_date", "", now or now_jst())

    def set_notify_time(self, notify_time: time, now: datetime | None = None) -> None:
        value = notify_time.strftime("%H:%M")
        self.db.set_setting("countdown_notify_time", value, now or now_jst())

    def days_left(self, today: date | None = None) -> int:
        return (self.exam_date() - (today or now_jst().date())).days

    def message(self, today: date | None = None) -> str:
        current = today or now_jst().date()
        exam = self.exam_date()
        remaining = (exam - current).days
        if remaining < 0:
            return "✅ 高専入試日は終了しました。"
        if remaining == 0:
            return (
                "🎓 *高専入試当日です*\n\n"
                "今日は高専入試の日です。\n"
                "落ち着いて、これまで勉強してきたことを出してきてください。"
            )
        if remaining == 1:
            return (
                "🔥 *高専入試まであと1日*\n\n"
                f"試験日：{format_japanese_date(exam)}\n\n"
                "いよいよ明日です。\n"
                "忘れ物と受験会場・時間を確認しておこう。"
            )
        return (
            f"📚 *高専入試まであと{remaining}日*\n\n"
            f"試験日：{format_japanese_date(exam)}\n\n"
            "今日も1日、少しずつ進めよう。"
        )

    def should_send_daily(self, now: datetime | None = None) -> bool:
        current = now or now_jst()
        if current.date() > self.exam_date():
            return False
        if current.time().replace(tzinfo=None) < self.notify_time():
            return False
        return self.db.get_setting("countdown_last_sent_date") != current.date().isoformat()

    def mark_daily_sent(self, now: datetime | None = None) -> None:
        current = now or now_jst()
        self.db.set_setting("countdown_last_sent_date", current.date().isoformat(), current)
