import { DefineFunction, Schema, SlackFunction } from "deno-slack-sdk/mod.ts";
import RemindersDatastore from "../datastores/reminders.ts";

export const ReminderDeleteFunction = DefineFunction({
  callback_id: "reminder_delete_function",
  title: "予定を削除",
  source_file: "functions/reminder_delete.ts",
  input_parameters: {
    properties: {
      reminder_id: { type: Schema.types.string },
      channel_id: { type: Schema.slack.types.channel_id },
      user_id: { type: Schema.slack.types.user_id },
    },
    required: ["reminder_id", "channel_id", "user_id"],
  },
});

export default SlackFunction(ReminderDeleteFunction, async ({ inputs, client }) => {
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
    return { error: "削除できる予定が見つかりません。" };
  }

  if (current.item.schedule_state === "scheduled" && current.item.scheduled_message_id) {
    const deleted = await client.chat.deleteScheduledMessage({
      channel: current.item.channel_id,
      scheduled_message_id: current.item.scheduled_message_id,
    });
    if (!deleted.ok) {
      return { error: `Slackの予約を取り消せませんでした: ${deleted.error ?? "unknown_error"}` };
    }
  }

  const saved = await client.apps.datastore.put({
    datastore: RemindersDatastore.name,
    item: {
      ...current.item,
      status: "deleted",
      revision: Number(current.item.revision ?? 0) + 1,
      schedule_state: "cancelled",
      scheduled_message_id: "",
      updated_at: Date.now(),
    },
  });
  if (!saved.ok) {
    return { error: `削除状態を保存できませんでした: ${saved.error ?? "unknown_error"}` };
  }

  await client.chat.postEphemeral({
    channel: inputs.channel_id,
    user: inputs.user_id,
    text: `🗑️ リマインダー \`${id}\` を削除しました。`,
  });
  return { outputs: {} };
});
