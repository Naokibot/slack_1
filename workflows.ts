import { DefineWorkflow, Schema } from "deno-slack-sdk/mod.ts";
import { KosenDailyFunction } from "./functions/kosen_daily.ts";
import { KosenSettingsFunction } from "./functions/kosen_settings.ts";
import { KosenStatusFunction } from "./functions/kosen_status.ts";
import { ReminderAddFunction } from "./functions/reminder_add.ts";
import { ReminderDeleteFunction } from "./functions/reminder_delete.ts";
import { ReminderEditFunction } from "./functions/reminder_edit.ts";
import { ReminderListFunction } from "./functions/reminder_list.ts";

const shortcutInputs = {
  properties: {
    interactivity: { type: Schema.slack.types.interactivity },
    channel_id: { type: Schema.slack.types.channel_id },
    user_id: { type: Schema.slack.types.user_id },
  },
  required: ["interactivity", "channel_id", "user_id"],
};

export const KosenDailyWorkflow = DefineWorkflow({
  callback_id: "kosen_daily_workflow",
  title: "高専カウントダウン日次処理",
  input_parameters: {
    properties: { revision: { type: Schema.types.string } },
    required: ["revision"],
  },
});
KosenDailyWorkflow.addStep(KosenDailyFunction, { revision: KosenDailyWorkflow.inputs.revision });

export const KosenSettingsWorkflow = DefineWorkflow({
  callback_id: "kosen_settings_workflow",
  title: "高専カウントダウン設定",
  input_parameters: shortcutInputs,
});
const kosenForm = KosenSettingsWorkflow.addStep(Schema.slack.functions.OpenForm, {
  title: "高専カウントダウン設定",
  interactivity: KosenSettingsWorkflow.inputs.interactivity,
  submit_label: "保存",
  fields: {
    elements: [
      { name: "exam_date", title: "試験日 (YYYY-MM-DD)", type: Schema.types.string },
      { name: "notify_time", title: "毎日の通知時刻 (HH:MM)", type: Schema.types.string },
      {
        name: "notification_channel",
        title: "通知先チャンネル",
        type: Schema.slack.types.channel_id,
      },
    ],
    required: ["exam_date", "notify_time", "notification_channel"],
  },
});
KosenSettingsWorkflow.addStep(KosenSettingsFunction, {
  exam_date: kosenForm.outputs.fields.exam_date,
  notify_time: kosenForm.outputs.fields.notify_time,
  notification_channel: kosenForm.outputs.fields.notification_channel,
  response_channel: KosenSettingsWorkflow.inputs.channel_id,
  user_id: KosenSettingsWorkflow.inputs.user_id,
});

export const KosenStatusWorkflow = DefineWorkflow({
  callback_id: "kosen_status_workflow",
  title: "高専入試までの日数を確認",
  input_parameters: shortcutInputs,
});
KosenStatusWorkflow.addStep(KosenStatusFunction, {
  channel_id: KosenStatusWorkflow.inputs.channel_id,
  user_id: KosenStatusWorkflow.inputs.user_id,
});

export const ReminderAddWorkflow = DefineWorkflow({
  callback_id: "reminder_add_workflow",
  title: "予定を追加",
  input_parameters: shortcutInputs,
});
const addForm = ReminderAddWorkflow.addStep(Schema.slack.functions.OpenForm, {
  title: "予定を追加",
  interactivity: ReminderAddWorkflow.inputs.interactivity,
  submit_label: "登録",
  fields: {
    elements: [
      { name: "title", title: "予定", type: Schema.types.string },
      { name: "date", title: "日付 (YYYY-MM-DD)", type: Schema.types.string },
      { name: "time", title: "時間 (HH:MM)", type: Schema.types.string },
      {
        name: "notification_channel",
        title: "通知先チャンネル",
        type: Schema.slack.types.channel_id,
      },
    ],
    required: ["title", "date", "time", "notification_channel"],
  },
});
ReminderAddWorkflow.addStep(ReminderAddFunction, {
  title: addForm.outputs.fields.title,
  date: addForm.outputs.fields.date,
  time: addForm.outputs.fields.time,
  notification_channel: addForm.outputs.fields.notification_channel,
  response_channel: ReminderAddWorkflow.inputs.channel_id,
  user_id: ReminderAddWorkflow.inputs.user_id,
});

export const ReminderListWorkflow = DefineWorkflow({
  callback_id: "reminder_list_workflow",
  title: "予定一覧",
  input_parameters: shortcutInputs,
});
const listForm = ReminderListWorkflow.addStep(Schema.slack.functions.OpenForm, {
  title: "予定一覧",
  interactivity: ReminderListWorkflow.inputs.interactivity,
  submit_label: "表示",
  fields: {
    elements: [
      {
        name: "range",
        title: "表示範囲 (all / today / tomorrow)",
        type: Schema.types.string,
      },
    ],
    required: ["range"],
  },
});
ReminderListWorkflow.addStep(ReminderListFunction, {
  range: listForm.outputs.fields.range,
  channel_id: ReminderListWorkflow.inputs.channel_id,
  user_id: ReminderListWorkflow.inputs.user_id,
});

export const ReminderEditWorkflow = DefineWorkflow({
  callback_id: "reminder_edit_workflow",
  title: "予定を編集",
  input_parameters: shortcutInputs,
});
const editForm = ReminderEditWorkflow.addStep(Schema.slack.functions.OpenForm, {
  title: "予定を編集",
  interactivity: ReminderEditWorkflow.inputs.interactivity,
  submit_label: "更新",
  fields: {
    elements: [
      { name: "reminder_id", title: "予定ID", type: Schema.types.string },
      { name: "title", title: "変更後の予定", type: Schema.types.string },
      { name: "date", title: "変更後の日付 (YYYY-MM-DD)", type: Schema.types.string },
      { name: "time", title: "変更後の時間 (HH:MM)", type: Schema.types.string },
      {
        name: "notification_channel",
        title: "通知先チャンネル",
        type: Schema.slack.types.channel_id,
      },
    ],
    required: ["reminder_id", "title", "date", "time", "notification_channel"],
  },
});
ReminderEditWorkflow.addStep(ReminderEditFunction, {
  reminder_id: editForm.outputs.fields.reminder_id,
  title: editForm.outputs.fields.title,
  date: editForm.outputs.fields.date,
  time: editForm.outputs.fields.time,
  notification_channel: editForm.outputs.fields.notification_channel,
  response_channel: ReminderEditWorkflow.inputs.channel_id,
  user_id: ReminderEditWorkflow.inputs.user_id,
});

export const ReminderDeleteWorkflow = DefineWorkflow({
  callback_id: "reminder_delete_workflow",
  title: "予定を削除",
  input_parameters: shortcutInputs,
});
const deleteForm = ReminderDeleteWorkflow.addStep(Schema.slack.functions.OpenForm, {
  title: "予定を削除",
  interactivity: ReminderDeleteWorkflow.inputs.interactivity,
  submit_label: "削除",
  fields: {
    elements: [{ name: "reminder_id", title: "予定ID", type: Schema.types.string }],
    required: ["reminder_id"],
  },
});
ReminderDeleteWorkflow.addStep(ReminderDeleteFunction, {
  reminder_id: deleteForm.outputs.fields.reminder_id,
  channel_id: ReminderDeleteWorkflow.inputs.channel_id,
  user_id: ReminderDeleteWorkflow.inputs.user_id,
});
