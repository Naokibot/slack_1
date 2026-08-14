import { TriggerTypes } from "deno-slack-api/mod.ts";
import { Trigger } from "deno-slack-api/types.ts";
import { KosenStatusWorkflow } from "../workflows.ts";

const trigger: Trigger<typeof KosenStatusWorkflow.definition> = {
  type: TriggerTypes.Shortcut,
  name: "高専入試まであと何日？",
  description: "現在の残り日数を表示",
  workflow: `#/workflows/${KosenStatusWorkflow.definition.callback_id}`,
  inputs: {
    interactivity: { value: "{{data.interactivity}}" },
    channel_id: { value: "{{data.channel_id}}" },
    user_id: { value: "{{data.user_id}}" },
  },
};

export default trigger;
