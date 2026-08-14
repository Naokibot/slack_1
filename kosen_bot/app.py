from __future__ import annotations

import logging
import signal
import sys

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .config import Config
from .countdown import CountdownService
from .db import Database
from .health import HealthServer
from .jma import JmaMonitor
from .notifier import SlackNotifier
from .reminders import ReminderService
from .slack_app import register_handlers
from .workers import WorkerSupervisor


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    config = Config.from_env()
    configure_logging(config.log_level)
    config.validate_runtime_secrets()

    db = Database(config.database_path)
    countdown = CountdownService(db, config.default_exam_date, config.default_notify_time)
    reminders = ReminderService(db)

    app = App(token=config.slack_bot_token)
    notifier = SlackNotifier(app.client)

    jma = JmaMonitor(
        db=db,
        post_earthquake=lambda text: notifier.post(config.earthquake_channel_id, text),
        post_warning=lambda text: notifier.post(config.shizuoka_alert_channel_id, text),
        post_admin=lambda text: notifier.post(config.admin_channel_id, text),
        max_backfill_hours=config.jma_backfill_hours,
    )

    def runtime_status() -> dict[str, object]:
        return {
            "status": "ok",
            "jma_last_success": jma.last_success.strftime("%Y-%m-%d %H:%M:%S") if jma.last_success else None,
        }

    register_handlers(app, config, db, countdown, reminders, runtime_status)

    workers = WorkerSupervisor(
        countdown=countdown,
        reminders=reminders,
        jma=jma,
        post_countdown=lambda text: notifier.post(config.countdown_channel_id, text),
        post_reminder=lambda channel, text: notifier.post(channel or config.reminder_channel_id, text),
        jma_poll_seconds=config.jma_poll_seconds,
        reminder_poll_seconds=config.reminder_poll_seconds,
    )
    health = HealthServer(config.health_port, runtime_status)
    workers.start()
    health.start()

    handler = SocketModeHandler(app, config.slack_app_token)

    def shutdown(signum, frame):
        logging.getLogger(__name__).info("Shutting down after signal %s", signum)
        workers.stop()
        health.stop()
        jma.client.close()
        handler.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    handler.start()


if __name__ == "__main__":
    main()
