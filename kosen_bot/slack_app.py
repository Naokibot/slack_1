from __future__ import annotations

from datetime import timedelta
from typing import Callable
import json

from slack_bolt import App

from .config import Config
from .countdown import CountdownService
from .db import Database
from .reminders import ReminderInput, ReminderService, format_reminder, parse_add_command, validate_title
from .timeutil import JST, format_japanese_date, now_jst, parse_clock, parse_user_date


def _help_text() -> str:
    return """🤖 *高専学習・防災Bot*

📚 *高専入試*
`/kosen`
`/kosen set-date YYYY-MM-DD`
`/kosen set-time HH:MM`

⏰ *リマインダー*
`/reminder add`
`/reminder add YYYY-MM-DD HH:MM 予定`
`/reminder list`
`/reminder today`
`/reminder tomorrow`
`/reminder edit ID`
`/reminder delete ID`

🌏 *防災*
`/disaster status`

🔧 *Bot*
`/bot-status`
`/kosen-help`"""


def _reminder_modal(callback_id: str, *, reminder_id: int | None = None, title: str = "", day: str = "", clock: str = "", channel_id: str = "", user_id: str = "") -> dict:
    metadata = json.dumps({"reminder_id": reminder_id, "channel_id": channel_id, "user_id": user_id}, ensure_ascii=False)
    title_element: dict = {"type": "plain_text_input", "action_id": "value", "multiline": False}
    if title:
        title_element["initial_value"] = title
    date_element: dict = {"type": "datepicker", "action_id": "value", "placeholder": {"type": "plain_text", "text": "日付"}}
    if day:
        date_element["initial_date"] = day
    time_element: dict = {"type": "timepicker", "action_id": "value", "placeholder": {"type": "plain_text", "text": "時間"}}
    if clock:
        time_element["initial_time"] = clock
    return {
        "type": "modal",
        "callback_id": callback_id,
        "private_metadata": metadata,
        "title": {"type": "plain_text", "text": "予定リマインダー"},
        "submit": {"type": "plain_text", "text": "保存"},
        "close": {"type": "plain_text", "text": "キャンセル"},
        "blocks": [
            {"type": "input", "block_id": "title", "label": {"type": "plain_text", "text": "予定"}, "element": title_element},
            {"type": "input", "block_id": "date", "label": {"type": "plain_text", "text": "日付"}, "element": date_element},
            {"type": "input", "block_id": "time", "label": {"type": "plain_text", "text": "時間"}, "element": time_element},
        ],
    }


def _extract_modal_input(body: dict) -> tuple[ReminderInput, dict]:
    view = body["view"]
    values = view["state"]["values"]
    title = validate_title(values["title"]["value"]["value"])
    day = parse_user_date(values["date"]["value"]["selected_date"])
    clock = parse_clock(values["time"]["value"]["selected_time"])
    metadata = json.loads(view.get("private_metadata") or "{}")
    return ReminderInput(title=title, day=day, clock=clock), metadata


def register_handlers(app: App, config: Config, db: Database, countdown: CountdownService, reminders: ReminderService, runtime_status: Callable[[], dict[str, object]]) -> None:
    def can_admin(user_id: str) -> bool:
        return not config.admin_user_ids or user_id in config.admin_user_ids

    @app.command("/kosen")
    def handle_kosen(ack, command, respond):
        ack()
        text = command.get("text", "").strip()
        if not text:
            respond(countdown.message())
            return
        parts = text.split()
        if parts[0] == "set-date" and len(parts) == 2:
            if not can_admin(command["user_id"]):
                respond("⚠️ この設定を変更する権限がありません。")
                return
            try:
                new_date = parse_user_date(parts[1])
            except ValueError as exc:
                respond(f"⚠️ {exc}")
                return
            countdown.set_exam_date(new_date)
            respond(f"✅ 高専入試日を {format_japanese_date(new_date)} に変更しました。")
            return
        if parts[0] == "set-time" and len(parts) == 2:
            if not can_admin(command["user_id"]):
                respond("⚠️ この設定を変更する権限がありません。")
                return
            try:
                new_time = parse_clock(parts[1])
            except ValueError as exc:
                respond(f"⚠️ {exc}")
                return
            countdown.set_notify_time(new_time)
            respond(f"✅ 毎日のカウントダウン通知時刻を {new_time:%H:%M} に変更しました。")
            return
        respond("⚠️ 使い方：`/kosen`、`/kosen set-date YYYY-MM-DD`、`/kosen set-time HH:MM`")

    @app.command("/reminder")
    def handle_reminder(ack, command, client, respond):
        ack()
        text = command.get("text", "").strip()
        channel_id = command.get("channel_id") or config.reminder_channel_id
        user_id = command.get("user_id", "")
        if not text or text == "add":
            client.views_open(
                trigger_id=command["trigger_id"],
                view=_reminder_modal("reminder_create", channel_id=channel_id, user_id=user_id),
            )
            return
        if text.startswith("add "):
            try:
                item = parse_add_command(text)
                reminder_id = reminders.create(item, channel_id, user_id)
            except ValueError as exc:
                respond(f"⚠️ {exc}\n\n例：`/reminder add 2026-08-20 19:00 数学の過去問`")
                return
            respond(
                "✅ *リマインダーを登録しました*\n\n"
                f"📝 予定：{item.title}\n📅 日付：{item.day:%Y年%m月%d日}\n🕖 時間：{item.clock:%H:%M}\n\nID：#{reminder_id}"
            )
            return
        if text == "list":
            items = reminders.list_all()
            if not items:
                respond("📅 登録されている予定はありません。")
                return
            respond("📅 *登録されている予定*\n\n" + "\n\n".join(format_reminder(item) for item in items[:50]))
            return
        if text in {"today", "tomorrow"}:
            day = now_jst().date() + (timedelta(days=1) if text == "tomorrow" else timedelta())
            items = reminders.list_for_day(day)
            label = "明日" if text == "tomorrow" else "今日"
            if not items:
                respond(f"📅 {label}の予定はありません。")
                return
            lines = [f"📅 *{label}の予定*", ""]
            lines.extend(f"{item.scheduled_at:%H:%M} {item.title}  `#{item.id}`" for item in items)
            respond("\n".join(lines))
            return
        if text.startswith("delete "):
            try:
                reminder_id = int(text.split(maxsplit=1)[1])
            except ValueError:
                respond("⚠️ 例：`/reminder delete 15`")
                return
            deleted = db.delete_reminder(reminder_id)
            if deleted is None:
                respond("⚠️ 該当する未完了リマインダーが見つかりません。")
                return
            respond("🗑️ *リマインダーを削除しました*\n\n" + format_reminder(deleted))
            return
        if text.startswith("edit "):
            try:
                reminder_id = int(text.split(maxsplit=1)[1])
            except ValueError:
                respond("⚠️ 例：`/reminder edit 15`")
                return
            reminder = db.get_reminder(reminder_id)
            if reminder is None or reminder.status != "pending":
                respond("⚠️ 該当する未完了リマインダーが見つかりません。")
                return
            when = reminder.scheduled_at.astimezone(JST)
            client.views_open(
                trigger_id=command["trigger_id"],
                view=_reminder_modal(
                    "reminder_edit",
                    reminder_id=reminder.id,
                    title=reminder.title,
                    day=when.date().isoformat(),
                    clock=when.strftime("%H:%M"),
                    channel_id=reminder.channel_id,
                    user_id=reminder.user_id,
                ),
            )
            return
        respond("⚠️ 不明な操作です。`/kosen-help` で使い方を確認してください。")

    @app.view("reminder_create")
    def handle_reminder_create(ack, body, client):
        try:
            item, metadata = _extract_modal_input(body)
            if item.scheduled_at <= now_jst():
                ack(response_action="errors", errors={"date": "未来の日時を指定してください"})
                return
        except ValueError as exc:
            ack(response_action="errors", errors={"title": str(exc)})
            return
        ack()
        channel_id = metadata.get("channel_id") or config.reminder_channel_id
        user_id = metadata.get("user_id") or body.get("user", {}).get("id", "")
        reminder_id = reminders.create(item, channel_id, user_id)
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=(
                "✅ *リマインダーを登録しました*\n\n"
                f"📝 予定：{item.title}\n📅 日付：{item.day:%Y年%m月%d日}\n🕖 時間：{item.clock:%H:%M}\n\nID：#{reminder_id}"
            ),
        )

    @app.view("reminder_edit")
    def handle_reminder_edit(ack, body, client):
        try:
            item, metadata = _extract_modal_input(body)
            if item.scheduled_at <= now_jst():
                ack(response_action="errors", errors={"date": "未来の日時を指定してください"})
                return
            reminder_id = int(metadata["reminder_id"])
        except (ValueError, KeyError, TypeError) as exc:
            ack(response_action="errors", errors={"title": f"入力を確認してください: {exc}"})
            return
        if not db.update_reminder(reminder_id, item.title, item.scheduled_at):
            ack(response_action="errors", errors={"title": "編集対象の予定が見つかりません"})
            return
        ack()
        channel_id = metadata.get("channel_id") or config.reminder_channel_id
        user_id = metadata.get("user_id") or body.get("user", {}).get("id", "")
        client.chat_postEphemeral(channel=channel_id, user=user_id, text=f"✅ リマインダー #{reminder_id} を更新しました。")

    @app.command("/disaster")
    def handle_disaster(ack, command, respond):
        ack()
        if command.get("text", "").strip() not in {"", "status"}:
            respond("⚠️ 使い方：`/disaster status`")
            return
        state = runtime_status()
        jma_last = state.get("jma_last_success") or "まだ取得していません"
        respond(
            "🌏 *防災監視ステータス*\n\n"
            "全国の震度5弱以上：監視中\n"
            "静岡県の警報・特別警報：監視中\n"
            f"気象庁最終取得：{jma_last}\n\n"
            "※通知がないことは安全を保証しません。"
        )

    @app.command("/bot-status")
    def handle_status(ack, respond):
        ack()
        state = runtime_status()
        respond(
            "🤖 *Bot Status*\n\n"
            "高専カウンター：正常\n"
            "予定リマインダー：正常\n"
            "地震監視：稼働中\n"
            "静岡県警報監視：稼働中\n"
            f"気象庁最終取得：{state.get('jma_last_success') or 'まだ取得していません'}\n"
            "DB：正常"
        )

    def handle_help(ack, respond):
        ack()
        respond(_help_text())

    app.command("/kosen-help")(handle_help)
    app.command("/help")(handle_help)
