import { DefineFunction, Schema, SlackFunction } from "deno-slack-sdk/mod.ts";
import RemindersDatastore from "../datastores/reminders.ts";
import { dateKey, jstDateParts } from "../lib/time.ts";

export const ReminderListFunction = DefineFunction({
  callback_id: "reminder_list_function",
  title: "予定一覧",
  source_file: "functions/reminder_list.ts",
  input_parameters: {
    properties: {
      range: { type: Schema.types.string },
      channel_id: { type: Schema.slack.types.channel_id },
      user_id: { type: Schema.slack.types.user_id },
    },
    required: ["range", "channel_id", "user_id"],
  },
});

export default SlackFunction(ReminderListFunction, async ({ inputs, client }) => {
  const result = await client.apps.datastore.query({
    datastore: RemindersDatastore.name,
    expression: "#status = :pending",
    expression_attributes: { "#status": "status" },
    expression_values: { ":pending": "pending" },
    limit: 100,
  });
  if (!result.ok) {
    return { error: `予定を取得できませんでした: ${result.error ?? "unknown_error"}` };
  }

  const now = new Date();
  const today = jstDateParts(now);
  const todayKey = dateKey(today);
  const tomorrow = new Date(Date.UTC(today.year, today.month - 1, today.day) + 86_400_000);
  const tomorrowKey = dateKey({
    year: tomorrow.getUTCFullYear(),
    month: tomorrow.getUTCMonth() + 1,
    day: tomorrow.getUTCDate(),
  });
  const range = inputs.range.trim().toLowerCase();
  if (!new Set(["all", "today", "tomorrow"]).has(range)) {
    return { error: "表示範囲は all / today / tomorrow のいずれかを入力してください。" };
  }

  const items = (result.items ?? [])
    .filter((item) => Number(item.scheduled_at) > now.getTime())
    .filter((item) =>
      range === "today"
        ? item.scheduled_date === todayKey
        : range === "tomorrow"
        ? item.scheduled_date === tomorrowKey
        : true
    )
    .sort((a, b) => Number(a.scheduled_at) - Number(b.scheduled_at));

  const label = range === "today" ? "今日の" : range === "tomorrow" ? "明日の" : "登録されている";
  const text = items.length === 0
    ? `📅 ${label}予定はありません。`
    : `📅 *${label}予定*\n\n${
      items.map((item) =>
        `• ${item.scheduled_date} ${item.scheduled_time}  ${item.title}\n  ID: \`${item.id}\``
      ).join("\n\n")
    }`;
  await client.chat.postEphemeral({ channel: inputs.channel_id, user: inputs.user_id, text });
  return { outputs: {} };
});
