import { TriggerTypes } from "deno-slack-api/mod.ts";
import { Trigger } from "deno-slack-api/types.ts";
import { ReminderEditWorkflow } from "../workflows.ts";

const trigger: Trigger<typeof ReminderEditWorkflow.definition> = {
  type: TriggerTypes.Shortcut,
  name: "予定を編集",
  description: "IDを指定して予定を変更",
  workflow: `#/workflows/${ReminderEditWorkflow.definition.callback_id}`,
  inputs: {
    interactivity: { value: "{{data.interactivity}}" },
    channel_id: { value: "{{data.channel_id}}" },
    user_id: { value: "{{data.user_id}}" },
  },
};

export default trigger;
