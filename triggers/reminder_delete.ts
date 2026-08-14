import { TriggerTypes } from "deno-slack-api/mod.ts";
import { Trigger } from "deno-slack-api/types.ts";
import { ReminderDeleteWorkflow } from "../workflows.ts";

const trigger: Trigger<typeof ReminderDeleteWorkflow.definition> = {
  type: TriggerTypes.Shortcut,
  name: "予定を削除",
  description: "IDを指定して予定を削除",
  workflow: `#/workflows/${ReminderDeleteWorkflow.definition.callback_id}`,
  inputs: {
    interactivity: { value: "{{data.interactivity}}" },
    channel_id: { value: "{{data.channel_id}}" },
    user_id: { value: "{{data.user_id}}" },
  },
};

export default trigger;
