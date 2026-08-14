import { DefineFunction, Schema, SlackFunction } from "deno-slack-sdk/mod.ts";
import SettingsDatastore from "../datastores/settings.ts";
import { nextJstOccurrence, parseDate, parseTime } from "../lib/time.ts";

export const KosenSettingsFunction = DefineFunction({
  callback_id: "kosen_settings_function",
  title: "高専カウントダウン設定",
  source_file: "functions/kosen_settings.ts",
  input_parameters: {
    properties: {
      exam_date: { type: Schema.types.string },
      notify_time: { type: Schema.types.string },
      notification_channel: { type: Schema.slack.types.channel_id },
      response_channel: { type: Schema.slack.types.channel_id },
      user_id: { type: Schema.slack.types.user_id },
    },
    required: ["exam_date", "notify_time", "notification_channel", "response_channel", "user_id"],
  },
});

export default SlackFunction(KosenSettingsFunction, async ({ inputs, client }) => {
  try {
    parseDate(inputs.exam_date);
    parseTime(inputs.notify_time);
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) };
  }

  const previous = await client.apps.datastore.get({
    datastore: SettingsDatastore.name,
    id: "global",
  });
  const oldItem = previous.item ?? {};
  const revision = Number(oldItem.revision ?? 0) + 1;
  const start = nextJstOccurrence(inputs.notify_time);

  const created = await client.workflows.triggers.create({
    type: "scheduled",
    name: "KOSEN daily countdown",
    description: "毎日の高専入試カウントダウンとリマインダー保守",
    workflow: "#/workflows/kosen_daily_workflow",
    schedule: {
      start_time: start.toISOString(),
      timezone: "Asia/Tokyo",
      frequency: { type: "daily", repeats_every: 1 },
    },
    inputs: { revision: { value: String(revision) } },
  });

  if (!created.ok || !created.trigger?.id) {
    return { error: `日次Triggerを作成できませんでした: ${created.error ?? "unknown_error"}` };
  }

  const saved = await client.apps.datastore.put({
    datastore: SettingsDatastore.name,
    item: {
      id: "global",
      exam_date: inputs.exam_date,
      notify_time: inputs.notify_time,
      channel_id: inputs.notification_channel,
      revision,
      daily_trigger_id: created.trigger.id,
      last_countdown_date: String(oldItem.last_countdown_date ?? ""),
      updated_at: Date.now(),
    },
  });
  if (!saved.ok) {
    await client.workflows.triggers.delete({ trigger_id: created.trigger.id });
    return { error: `設定を保存できませんでした: ${saved.error ?? "unknown_error"}` };
  }

  let oldTriggerWarning = "";
  if (typeof oldItem.daily_trigger_id === "string" && oldItem.daily_trigger_id) {
    const removed = await client.workflows.triggers.delete({
      trigger_id: oldItem.daily_trigger_id,
    });
    if (!removed.ok) {
      oldTriggerWarning =
        "\n⚠️ 古いTriggerの削除に失敗しましたが、旧設定からの通知は無効化されます。";
    }
  }

  await client.chat.postEphemeral({
    channel: inputs.response_channel,
    user: inputs.user_id,
    text:
      `✅ *高専カウントダウンを設定しました*\n\n試験日：${inputs.exam_date}\n毎日：${inputs.notify_time}\n通知先：<#${inputs.notification_channel}>${oldTriggerWarning}`,
  });

  return { outputs: {} };
});
