from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
import os
from pathlib import Path

from dotenv import load_dotenv


def _parse_date(value: str, fallback: date) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return fallback


def _parse_time(value: str, fallback: time) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError:
        return fallback


@dataclass(frozen=True)
class Config:
    slack_bot_token: str
    slack_app_token: str
    countdown_channel_id: str
    reminder_channel_id: str
    earthquake_channel_id: str
    shizuoka_alert_channel_id: str
    admin_channel_id: str
    admin_user_ids: frozenset[str]
    database_path: Path
    default_exam_date: date
    default_notify_time: time
    jma_poll_seconds: int
    jma_backfill_hours: int
    reminder_poll_seconds: int
    health_port: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        admins = frozenset(
            item.strip()
            for item in os.getenv("ADMIN_USER_IDS", "").split(",")
            if item.strip()
        )
        return cls(
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN", "").strip(),
            slack_app_token=os.getenv("SLACK_APP_TOKEN", "").strip(),
            countdown_channel_id=os.getenv("COUNTDOWN_CHANNEL_ID", "").strip(),
            reminder_channel_id=os.getenv("REMINDER_CHANNEL_ID", "").strip(),
            earthquake_channel_id=os.getenv("EARTHQUAKE_CHANNEL_ID", "").strip(),
            shizuoka_alert_channel_id=os.getenv("SHIZUOKA_ALERT_CHANNEL_ID", "").strip(),
            admin_channel_id=os.getenv("ADMIN_CHANNEL_ID", "").strip(),
            admin_user_ids=admins,
            database_path=Path(os.getenv("DATABASE_PATH", "data/bot.sqlite3")),
            default_exam_date=_parse_date(os.getenv("KOSEN_EXAM_DATE", "2027-02-14"), date(2027, 2, 14)),
            default_notify_time=_parse_time(os.getenv("KOSEN_NOTIFY_TIME", "07:00"), time(7, 0)),
            jma_poll_seconds=max(30, int(os.getenv("JMA_POLL_SECONDS", "60"))),
            jma_backfill_hours=max(1, int(os.getenv("JMA_BACKFILL_HOURS", "6"))),
            reminder_poll_seconds=max(5, int(os.getenv("REMINDER_POLL_SECONDS", "15"))),
            health_port=max(0, int(os.getenv("HEALTH_PORT", "8080"))),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def validate_runtime_secrets(self) -> None:
        required = {
            "SLACK_BOT_TOKEN": self.slack_bot_token,
            "SLACK_APP_TOKEN": self.slack_app_token,
            "COUNTDOWN_CHANNEL_ID": self.countdown_channel_id,
            "REMINDER_CHANNEL_ID": self.reminder_channel_id,
            "EARTHQUAKE_CHANNEL_ID": self.earthquake_channel_id,
            "SHIZUOKA_ALERT_CHANNEL_ID": self.shizuoka_alert_channel_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError("Missing required environment variables: " + ", ".join(missing))
