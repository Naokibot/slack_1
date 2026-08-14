from datetime import date, datetime, time
from pathlib import Path

from kosen_bot.countdown import CountdownService
from kosen_bot.db import Database
from kosen_bot.timeutil import JST


def test_countdown_days_and_daily_once(tmp_path: Path):
    db = Database(tmp_path / "bot.db")
    service = CountdownService(db, date(2027, 2, 14), time(7, 0))
    now = datetime(2026, 8, 14, 7, 0, tzinfo=JST)
    assert service.days_left(now.date()) == 184
    assert "あと184日" in service.message(now.date())
    assert service.should_send_daily(now)
    service.mark_daily_sent(now)
    assert not service.should_send_daily(datetime(2026, 8, 14, 20, 0, tzinfo=JST))
    assert service.should_send_daily(datetime(2026, 8, 15, 8, 0, tzinfo=JST))


def test_countdown_special_messages(tmp_path: Path):
    service = CountdownService(Database(tmp_path / "bot.db"), date(2027, 2, 14), time(7, 0))
    assert "あと1日" in service.message(date(2027, 2, 13))
    assert "入試当日" in service.message(date(2027, 2, 14))
    assert not service.should_send_daily(datetime(2027, 2, 15, 8, 0, tzinfo=JST))
