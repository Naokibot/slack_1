import { DefineFunction, Schema, SlackFunction } from "deno-slack-sdk/mod.ts";
import SettingsDatastore from "../datastores/settings.ts";
import RemindersDatastore from "../datastores/reminders.ts";
import { countdownMessage } from "../lib/messages.ts";
import { insideScheduleHorizon, scheduleSlackMessage } from "../lib/reminder_schedule.ts";
import { dateKey, jstDateParts } from "../lib/time.ts";

export const KosenDailyFunction = DefineFunction({
  callback_id: "kosen_daily_function",
  title: "高専カウントダウン日次処理",
  source_file: "functions/kosen_daily.ts",
  input_parameters: {
    properties: { revision: { type: Schema.types.string } },
    required: ["revision"],
  },
});

export default SlackFunction(KosenDailyFunction, async ({ inputs, client }) => {
  const settingsResult = await client.apps.datastore.get({
    datastore: SettingsDatastore.name,
    id: "global",
  });
  if (!settingsResult.ok || !settingsResult.item) return { outputs: {} };
  const settings = settingsResult.item;
  if (Number(inputs.revision) !== Number(settings.revision)) return { outputs: {} };

  const now = Date.now();
  const pending = await client.apps.datastore.query({
    datastore: RemindersDatastore.name,
    expression: "#status = :pending",
    expression_attributes: { "#status": "status" },
    expression_values: { ":pending": "pending" },
    limit: 100,
  });

  if (pending.ok) {
    for (const reminder of pending.items ?? []) {
      const at = Number(reminder.scheduled_at);
      if (at <= now && reminder.schedule_state === "scheduled") {
        await client.apps.datastore.put({
          datastore: RemindersDatastore.name,
          item: { ...reminder, status: "notified", notified_at: now, updated_at: now },
        });
        continue;
      }
      if (reminder.schedule_state === "queued" && at > now && insideScheduleHorizon(at, now)) {
        try {
          const scheduledMessageId = await scheduleSlackMessage(client, {
            title: String(reminder.title),
            scheduled_at: at,
            scheduled_date: String(reminder.scheduled_date),
            scheduled_time: String(reminder.scheduled_time),
            channel_id: String(reminder.channel_id),
          });
          await client.apps.datastore.put({
            datastore: RemindersDatastore.name,
            item: {
              ...reminder,
              schedule_state: "scheduled",
              scheduled_message_id: scheduledMessageId,
              updated_at: now,
            },
          });
        } catch (error) {
          console.error("Failed to schedule queued reminder", reminder.id, error);
        }
      }
    }
  }

  const today = dateKey(jstDateParts(new Date(now)));
  if (settings.last_countdown_date === today) return { outputs: {} };
  const message = countdownMessage(String(settings.exam_date), new Date(now));
  if (!message) return { outputs: {} };

  const posted = await client.chat.postMessage({ channel: settings.channel_id, text: message });
  if (!posted.ok) {
    return { error: `カウントダウン投稿に失敗しました: ${posted.error ?? "unknown_error"}` };
  }

  await client.apps.datastore.put({
    datastore: SettingsDatastore.name,
    item: { ...settings, last_countdown_date: today, updated_at: now },
  });
  return { outputs: {} };
});
