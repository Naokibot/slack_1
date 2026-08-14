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
                """
            )

    def get_setting(self, key: str) -> str | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            ).fetchone()
        return None if row is None else str(row["value"])

    def set_setting(self, key: str, value: str, updated_at: datetime) -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (key, value, updated_at.isoformat()),
            )

    def add_reminder(
        self,
        title: str,
        scheduled_at: datetime,
        channel_id: str,
        user_id: str,
        created_at: datetime,
    ) -> int:
        with self.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO reminders(
                    title,
                    scheduled_at,
                    channel_id,
                    user_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    title,
                    scheduled_at.isoformat(),
                    channel_id,
                    user_id,
                    created_at.isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def get_reminder(self, reminder_id: int) -> Reminder | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM reminders WHERE id = ?",
                (reminder_id,),
            ).fetchone()
        return None if row is None else self._row_to_reminder(row)

    def list_reminders(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Reminder]:
        conditions = ["status = 'pending'"]
        params: list[str] = []
        if start is not None:
            conditions.append("scheduled_at >= ?")
            params.append(start.isoformat())
        if end is not None:
            conditions.append("scheduled_at < ?")
            params.append(end.isoformat())

        sql = (
            "SELECT * FROM reminders WHERE "
            + " AND ".join(conditions)
            + " ORDER BY scheduled_at, id"
        )
        with self.connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [self._row_to_reminder(row) for row in rows]

    def due_reminders(
        self,
        earliest: datetime,
        latest: datetime,
    ) -> list[Reminder]:
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

    def mark_reminder_notified(
        self,
        reminder_id: int,
        notified_at: datetime,
    ) -> None:
        with self.connect() as db:
            db.execute(
                """
                UPDATE reminders
                SET status='notified', notified_at=?
                WHERE id=? AND status='pending'
                """,
                (notified_at.isoformat(), reminder_id),
            )

    def expire_old_reminders(self, before: datetime) -> int:
        with self.connect() as db:
            cursor = db.execute(
                """
                UPDATE reminders
                SET status='expired'
                WHERE status='pending' AND scheduled_at < ?
                """,
                (before.isoformat(),),
            )
            return int(cursor.rowcount)

    def delete_reminder(self, reminder_id: int) -> Reminder | None:
        reminder = self.get_reminder(reminder_id)
        if reminder is None or reminder.status != "pending":
            return None

        with self.connect() as db:
            db.execute(
                """
                UPDATE reminders
                SET status='deleted'
                WHERE id=? AND status='pending'
                """,
                (reminder_id,),
            )
        return reminder

    def update_reminder(
        self,
        reminder_id: int,
        title: str,
        scheduled_at: datetime,
    ) -> bool:
        with self.connect() as db:
            cursor = db.execute(
                """
                UPDATE reminders
                SET title=?, scheduled_at=?
                WHERE id=? AND status='pending'
                """,
                (title, scheduled_at.isoformat(), reminder_id),
            )
            return cursor.rowcount == 1

    @staticmethod
    def _row_to_reminder(row: sqlite3.Row) -> Reminder:
        return Reminder(
            id=int(row["id"]),
            title=str(row["title"]),
            scheduled_at=datetime.fromisoformat(str(row["scheduled_at"])),
            channel_id=str(row["channel_id"]),
            user_id=str(row["user_id"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            notified_at=(
                datetime.fromisoformat(str(row["notified_at"]))
                if row["notified_at"]
                else None
            ),
            status=str(row["status"]),
        )
