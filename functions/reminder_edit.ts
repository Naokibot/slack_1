import { DefineFunction, Schema, SlackFunction } from "deno-slack-sdk/mod.ts";
import RemindersDatastore from "../datastores/reminders.ts";
import { insideScheduleHorizon, scheduleSlackMessage } from "../lib/reminder_schedule.ts";
import { jstDateTime } from "../lib/time.ts";

export const ReminderEditFunction = DefineFunction({
  callback_id: "reminder_edit_function",
  title: "予定を編集",
  source_file: "functions/reminder_edit.ts",
  input_parameters: {
    properties: {
      reminder_id: { type: Schema.types.string },
      title: { type: Schema.types.string },
      date: { type: Schema.types.string },
      time: { type: Schema.types.string },
      notification_channel: { type: Schema.slack.types.channel_id },
      response_channel: { type: Schema.slack.types.channel_id },
      user_id: { type: Schema.slack.types.user_id },
    },
    required: [
      "reminder_id",
      "title",
      "date",
      "time",
      "notification_channel",
      "response_channel",
      "user_id",
    ],
  },
});

export default SlackFunction(ReminderEditFunction, async ({ inputs, client }) => {
  const id = inputs.reminder_id.trim();
  const current = await client.apps.datastore.get({
    datastore: RemindersDatastore.name,
    id,
  });
  if (!current.ok) {
    return { error: `予定を取得できませんでした: ${current.error ?? "unknown_error"}` };
  }
  if (
    !current.item || current.item.status !== "pending" ||
    String(current.item.user_id) !== inputs.user_id
  ) {
    return { error: "編集できる予定が見つかりません。" };
  }

  const title = inputs.title.trim();
  if (!title || title.length > 300) {
    return { error: "予定は1〜300文字で入力してください。" };
  }

  let at: Date;
  try {
    at = jstDateTime(inputs.date, inputs.time);
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }
  if (at.getTime() <= Date.now() + 30_000) {
    return { error: "未来の日時を指定してください。" };
  }

  let newScheduledMessageId = "";
  let newState = "queued";
  if (insideScheduleHorizon(at.getTime())) {
    try {
      newScheduledMessageId = await scheduleSlackMessage(client, {
        title,
        scheduled_at: at.getTime(),
        scheduled_date: inputs.date,
        scheduled_time: inputs.time,
        channel_id: inputs.notification_channel,
      });
      newState = "scheduled";
    } catch (error) {
      return { error: error instanceof Error ? error.message : String(error) };
    }
  }

  if (current.item.schedule_state === "scheduled" && current.item.scheduled_message_id) {
    const deleted = await client.chat.deleteScheduledMessage({
      channel: current.item.channel_id,
      scheduled_message_id: current.item.scheduled_message_id,
    });
    if (!deleted.ok) {
      if (newScheduledMessageId) {
        await client.chat.deleteScheduledMessage({
          channel: inputs.notification_channel,
          scheduled_message_id: newScheduledMessageId,
        });
      }
      return { error: `元の予約を取り消せませんでした: ${deleted.error ?? "unknown_error"}` };
    }
  }

  const saved = await client.apps.datastore.put({
    datastore: RemindersDatastore.name,
    item: {
      ...current.item,
      title,
      scheduled_at: at.getTime(),
      scheduled_date: inputs.date,
      scheduled_time: inputs.time,
      channel_id: inputs.notification_channel,
      revision: Number(current.item.revision ?? 0) + 1,
      schedule_state: newState,
      scheduled_message_id: newScheduledMessageId,
      updated_at: Date.now(),
    },
  });
  if (!saved.ok) {
    if (newScheduledMessageId) {
      await client.chat.deleteScheduledMessage({
        channel: inputs.notification_channel,
        scheduled_message_id: newScheduledMessageId,
      });
    }
    return {
      error:
        `更新を保存できませんでした: ${saved.error ?? "unknown_error"}。元のSlack予約は取り消されているため、予定を再登録してください。`,
    };
  }

  await client.chat.postEphemeral({
    channel: inputs.response_channel,
    user: inputs.user_id,
    text: `✅ リマインダー \`${id}\` を更新しました。`,
  });
  return { outputs: {} };
});
