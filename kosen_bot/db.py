from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import sqlite3
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class Reminder:
    id: int
    title: str
    scheduled_at: datetime
    channel_id: str
    user_id: str
    created_at: datetime
    notified_at: datetime | None
    status: str


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 300),
                    scheduled_at TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    notified_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending', 'notified', 'deleted', 'expired'))
                );
                CREATE INDEX IF NOT EXISTS idx_reminders_due
                    ON reminders(status, scheduled_at);

                CREATE TABLE IF NOT EXISTS processed_jma_entries (
                    entry_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    processed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS earthquake_events (
                    event_id TEXT PRIMARY KEY,
                    max_intensity TEXT NOT NULL,
                    magnitude TEXT,
                    tsunami_text TEXT,
                    fingerprint TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS warning_state (
                    alert_name TEXT NOT NULL,
                    area_name TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(alert_name, area_name)
                );
                """
            )

    def get_setting(self, key: str) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set_setting(self, key: str, value: str, updated_at: datetime) -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, value, updated_at.isoformat()),
            )

    def add_reminder(self, title: str, scheduled_at: datetime, channel_id: str, user_id: str, created_at: datetime) -> int:
        with self.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO reminders(title, scheduled_at, channel_id, user_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, scheduled_at.isoformat(), channel_id, user_id, created_at.isoformat()),
            )
            return int(cursor.lastrowid)

    def get_reminder(self, reminder_id: int) -> Reminder | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        return None if row is None else self._row_to_reminder(row)

    def list_reminders(self, start: datetime | None = None, end: datetime | None = None) -> list[Reminder]:
        conditions = ["status = 'pending'"]
        params: list[str] = []
        if start is not None:
            conditions.append("scheduled_at >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("scheduled_at < ?")
            params.append(end.isoformat())
        sql = "SELECT * FROM reminders WHERE " + " AND ".join(conditions) + " ORDER BY scheduled_at, id"
        with self.connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [self._row_to_reminder(row) for row in rows]

    def due_reminders(self, earliest: datetime, latest: datetime) -> list[Reminder]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT * FROM reminders
                WHERE status='pending' AND scheduled_at BETWEEN ? AND ?
                ORDER BY scheduled_at, id
                """,
                (earliest.isoformat(), latest.isoformat()),
            ).fetchall()
        return [self._row_to_reminder(row) for row in rows]

    def mark_reminder_notified(self, reminder_id: int, notified_at: datetime) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE reminders SET status='notified', notified_at=? WHERE id=? AND status='pending'",
                (notified_at.isoformat(), reminder_id),
            )

    def expire_old_reminders(self, before: datetime) -> int:
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE reminders SET status='expired' WHERE status='pending' AND scheduled_at < ?",
                (before.isoformat(),),
            )
            return int(cursor.rowcount)

    def delete_reminder(self, reminder_id: int) -> Reminder | None:
        reminder = self.get_reminder(reminder_id)
        if reminder is None or reminder.status != "pending":
            return None
        with self.connect() as db:
            db.execute("UPDATE reminders SET status='deleted' WHERE id=? AND status='pending'", (reminder_id,))
        return reminder

    def update_reminder(self, reminder_id: int, title: str, scheduled_at: datetime) -> bool:
        with self.connect() as db:
            cursor = db.execute(
                """
                UPDATE reminders SET title=?, scheduled_at=?
                WHERE id=? AND status='pending'
                """,
                (title, scheduled_at.isoformat(), reminder_id),
            )
            return cursor.rowcount == 1

    def has_processed_jma_entry(self, entry_id: str) -> bool:
        with self.connect() as db:
            row = db.execute("SELECT 1 FROM processed_jma_entries WHERE entry_id=?", (entry_id,)).fetchone()
        return row is not None

    def mark_jma_entry_processed(self, entry_id: str, category: str, processed_at: datetime) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO processed_jma_entries(entry_id, category, processed_at) VALUES (?, ?, ?)",
                (entry_id, category, processed_at.isoformat()),
            )

    def get_earthquake_event(self, event_id: str) -> sqlite3.Row | None:
        with self.connect() as db:
            return db.execute("SELECT * FROM earthquake_events WHERE event_id=?", (event_id,)).fetchone()

    def upsert_earthquake_event(self, event_id: str, max_intensity: str, magnitude: str | None, tsunami_text: str | None, fingerprint: str, updated_at: datetime) -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO earthquake_events(event_id, max_intensity, magnitude, tsunami_text, fingerprint, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                  max_intensity=excluded.max_intensity,
                  magnitude=excluded.magnitude,
                  tsunami_text=excluded.tsunami_text,
                  fingerprint=excluded.fingerprint,
                  updated_at=excluded.updated_at
                """,
                (event_id, max_intensity, magnitude, tsunami_text, fingerprint, updated_at.isoformat()),
            )

    def get_warning_active(self, alert_name: str, area_name: str) -> bool:
        with self.connect() as db:
            row = db.execute(
                "SELECT active FROM warning_state WHERE alert_name=? AND area_name=?",
                (alert_name, area_name),
            ).fetchone()
        return bool(row["active"]) if row is not None else False

    def set_warning_active(self, alert_name: str, area_name: str, active: bool, updated_at: datetime) -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO warning_state(alert_name, area_name, active, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(alert_name, area_name) DO UPDATE SET
                  active=excluded.active, updated_at=excluded.updated_at
                """,
                (alert_name, area_name, int(active), updated_at.isoformat()),
            )

    @staticmethod
    def _row_to_reminder(row: sqlite3.Row) -> Reminder:
        return Reminder(
            id=int(row["id"]),
            title=str(row["title"]),
            scheduled_at=datetime.fromisoformat(str(row["scheduled_at"])),
            channel_id=str(row["channel_id"]),
            user_id=str(row["user_id"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            notified_at=datetime.fromisoformat(str(row["notified_at"])) if row["notified_at"] else None,
            status=str(row["status"]),
        )
