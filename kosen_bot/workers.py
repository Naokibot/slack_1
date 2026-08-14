from __future__ import annotations

from datetime import timedelta
import logging
import threading
from typing import Callable

from .countdown import CountdownService
from .reminders import ReminderService
from .timeutil import now_jst

LOGGER = logging.getLogger(__name__)


class WorkerSupervisor:
    def __init__(
        self,
        countdown: CountdownService,
        reminders: ReminderService,
        post_countdown: Callable[[str], None],
        post_reminder: Callable[[str, str], None],
        reminder_poll_seconds: int,
    ):
        self.countdown = countdown
        self.reminders = reminders
        self.post_countdown = post_countdown
        self.post_reminder = post_reminder
        self.reminder_poll_seconds = reminder_poll_seconds
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []

    def start(self) -> None:
        self.threads = [
            threading.Thread(
                target=self._guarded,
                args=("countdown", self._countdown_loop),
                daemon=True,
            ),
            threading.Thread(
                target=self._guarded,
                args=("reminders", self._reminder_loop),
                daemon=True,
            ),
        ]
        for thread in self.threads:
            thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=5)

    def _guarded(self, name: str, worker: Callable[[], None]) -> None:
        backoff = 1
        while not self.stop_event.is_set():
            try:
                worker()
                return
            except Exception:
                LOGGER.exception("Worker %s crashed; restarting", name)
                self.stop_event.wait(backoff)
                backoff = min(backoff * 2, 60)

    def _countdown_loop(self) -> None:
        while not self.stop_event.is_set():
            current = now_jst()
            if self.countdown.should_send_daily(current):
                self.post_countdown(self.countdown.message(current.date()))
                self.countdown.mark_daily_sent(current)
                LOGGER.info("Daily KOSEN countdown sent")
            self.stop_event.wait(20)

    def _reminder_loop(self) -> None:
        while not self.stop_event.is_set():
            current = now_jst()
            for reminder in self.reminders.due(current):
                late = current - reminder.scheduled_at
                prefix = (
                    "⏰ *遅延したリマインダー*"
                    if late >= timedelta(minutes=1)
                    else "⏰ *リマインダー*"
                )
                lines = [
                    prefix,
                    "",
                    reminder.title,
                    "",
                    f"📅 {reminder.scheduled_at:%Y年%m月%d日}",
                    f"🕖 {reminder.scheduled_at:%H:%M}",
                ]
                if late >= timedelta(minutes=1):
                    lines.extend(
                        ["", "Bot停止中または通信障害中に予定時刻を過ぎました。"]
                    )
                self.post_reminder(reminder.channel_id, "\n".join(lines))
                self.reminders.db.mark_reminder_notified(reminder.id, current)
                LOGGER.info("Reminder %s sent", reminder.id)

            expired = self.reminders.expire_stale(current)
            if expired:
                LOGGER.warning("Expired %s stale reminder(s)", expired)
            self.stop_event.wait(self.reminder_poll_seconds)
