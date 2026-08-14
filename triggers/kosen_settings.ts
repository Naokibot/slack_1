import { TriggerTypes } from "deno-slack-api/mod.ts";
import { Trigger } from "deno-slack-api/types.ts";
import { KosenSettingsWorkflow } from "../workflows.ts";

const trigger: Trigger<typeof KosenSettingsWorkflow.definition> = {
  type: TriggerTypes.Shortcut,
  name: "高専カウントダウン設定",
  description: "試験日・毎日の通知時刻・通知先を設定",
  workflow: `#/workflows/${KosenSettingsWorkflow.definition.callback_id}`,
  inputs: {
    interactivity: { value: "{{data.interactivity}}" },
    channel_id: { value: "{{data.channel_id}}" },
    user_id: { value: "{{data.user_id}}" },
  },
};

export default trigger;
