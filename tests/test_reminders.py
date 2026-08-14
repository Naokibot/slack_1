from datetime import date, datetime
from pathlib import Path

import pytest

from kosen_bot.db import Database
from kosen_bot.reminders import ReminderService, parse_add_command
from kosen_bot.timeutil import JST, parse_user_date


def test_parse_add_command_and_short_dates():
    item = parse_add_command("add 2026-08-20 19:00 数学の過去問", today=date(2026, 8, 14))
    assert item.title == "数学の過去問"
    assert item.day == date(2026, 8, 20)
    assert item.clock.hour == 19
    assert parse_user_date("today", today=date(2026, 8, 14)) == date(2026, 8, 14)
    assert parse_user_date("tomorrow", today=date(2026, 8, 14)) == date(2026, 8, 15)
    assert parse_user_date("8/20", today=date(2026, 8, 14)) == date(2026, 8, 20)


def test_missing_time_is_rejected():
    with pytest.raises(ValueError):
        parse_add_command("add 2026-08-20 数学", today=date(2026, 8, 14))


def test_reminder_lifecycle_and_due_window(tmp_path: Path):
    db = Database(tmp_path / "bot.db")
    service = ReminderService(db)
    current = datetime(2026, 8, 14, 18, 0, tzinfo=JST)
    item = parse_add_command("add 2026-08-14 18:10 数学", today=current.date())
    reminder_id = service.create(item, "C1", "U1", now=current)
    assert db.get_reminder(reminder_id) is not None
    assert service.due(datetime(2026, 8, 14, 18, 10, 5, tzinfo=JST))[0].id == reminder_id
    db.mark_reminder_notified(reminder_id, datetime(2026, 8, 14, 18, 10, 5, tzinfo=JST))
    assert service.due(datetime(2026, 8, 14, 18, 11, tzinfo=JST)) == []


def test_restart_late_window_and_expiry(tmp_path: Path):
    db = Database(tmp_path / "bot.db")
    service = ReminderService(db)
    current = datetime(2026, 8, 14, 19, 0, tzinfo=JST)
    recent = parse_add_command("add 2026-08-14 19:10 最近", today=current.date())
    old = parse_add_command("add 2026-08-14 19:20 古い", today=current.date())
    recent_id = service.create(recent, "C1", "U1", now=current)
    old_id = service.create(old, "C1", "U1", now=current)
    check = datetime(2026, 8, 14, 19, 35, tzinfo=JST)
    due_ids = {r.id for r in service.due(check)}
    assert recent_id in due_ids
    assert old_id in due_ids
    stale_item = parse_add_command("add 2026-08-14 19:40 stale", today=current.date())
    stale_id = service.create(stale_item, "C1", "U1", now=current)
    assert service.expire_stale(datetime(2026, 8, 14, 20, 11, tzinfo=JST)) >= 1
    assert db.get_reminder(stale_id).status == "expired"
