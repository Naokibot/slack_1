import { DefineFunction, Schema, SlackFunction } from "deno-slack-sdk/mod.ts";
import RemindersDatastore from "../datastores/reminders.ts";
import {
  insideScheduleHorizon,
  MAX_PENDING_REMINDERS,
  scheduleSlackMessage,
} from "../lib/reminder_schedule.ts";
import { jstDateTime } from "../lib/time.ts";

export const ReminderAddFunction = DefineFunction({
  callback_id: "reminder_add_function",
  title: "予定を追加",
  source_file: "functions/reminder_add.ts",
  input_parameters: {
    properties: {
      title: { type: Schema.types.string },
      date: { type: Schema.types.string },
      time: { type: Schema.types.string },
      notification_channel: { type: Schema.slack.types.channel_id },
      response_channel: { type: Schema.slack.types.channel_id },
      user_id: { type: Schema.slack.types.user_id },
    },
    required: [
      "title",
      "date",
      "time",
      "notification_channel",
      "response_channel",
      "user_id",
    ],
  },
});

export default SlackFunction(ReminderAddFunction, async ({ inputs, client }) => {
  const title = inputs.title.trim();
  if (!title || title.length > 300) {
    return { error: "予定は1〜300文字で入力してください。" };
  }

  let scheduled: Date;
  try {
    scheduled = jstDateTime(inputs.date, inputs.time);
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }
  if (scheduled.getTime() <= Date.now() + 30_000) {
    return { error: "未来の日時を指定してください。" };
  }

  const pending = await client.apps.datastore.query({
    datastore: RemindersDatastore.name,
    expression: "#status = :pending",
    expression_attributes: { "#status": "status" },
    expression_values: { ":pending": "pending" },
    limit: MAX_PENDING_REMINDERS,
  });
  if (!pending.ok) {
    return { error: `予定件数を確認できませんでした: ${pending.error ?? "unknown_error"}` };
  }

  const ownPendingCount = (pending.items ?? []).filter(
    (item) => String(item.user_id) === inputs.user_id,
  ).length;
  if (ownPendingCount >= MAX_PENDING_REMINDERS) {
    return { error: `未完了の予定は1ユーザー最大${MAX_PENDING_REMINDERS}件です。` };
  }

  const id = crypto.randomUUID();
  const now = Date.now();
  let scheduleState = "queued";
  let scheduledMessageId = "";
  if (insideScheduleHorizon(scheduled.getTime(), now)) {
    try {
      scheduledMessageId = await scheduleSlackMessage(client, {
        title,
        scheduled_at: scheduled.getTime(),
        scheduled_date: inputs.date,
        scheduled_time: inputs.time,
        channel_id: inputs.notification_channel,
      });
      scheduleState = "scheduled";
    } catch (error) {
      return { error: error instanceof Error ? error.message : String(error) };
    }
  }

  const put = await client.apps.datastore.put({
    datastore: RemindersDatastore.name,
    item: {
      id,
      title,
      scheduled_at: scheduled.getTime(),
      scheduled_date: inputs.date,
      scheduled_time: inputs.time,
      channel_id: inputs.notification_channel,
      user_id: inputs.user_id,
      status: "pending",
      revision: 1,
      schedule_state: scheduleState,
      scheduled_message_id: scheduledMessageId,
      created_at: now,
      updated_at: now,
      notified_at: 0,
    },
  });
  if (!put.ok) {
    if (scheduledMessageId) {
      await client.chat.deleteScheduledMessage({
        channel: inputs.notification_channel,
        scheduled_message_id: scheduledMessageId,
      });
    }
    return { error: `予定を保存できませんでした: ${put.error ?? "unknown_error"}` };
  }

  const queueNote = scheduleState === "queued"
    ? "\n※先の日付のためDatastoreで待機し、日次処理が自動予約します。"
    : "";
  await client.chat.postEphemeral({
    channel: inputs.response_channel,
    user: inputs.user_id,
    text:
      `✅ *リマインダーを登録しました*\n\n📝 ${title}\n📅 ${inputs.date}\n🕖 ${inputs.time}\nID：\`${id}\`${queueNote}`,
  });
  return { outputs: {} };
});
