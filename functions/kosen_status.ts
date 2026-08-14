import { DefineFunction, Schema, SlackFunction } from "deno-slack-sdk/mod.ts";
import SettingsDatastore from "../datastores/settings.ts";
import { countdownMessage } from "../lib/messages.ts";

export const KosenStatusFunction = DefineFunction({
  callback_id: "kosen_status_function",
  title: "高専カウントダウンを確認",
  source_file: "functions/kosen_status.ts",
  input_parameters: {
    properties: {
      channel_id: { type: Schema.slack.types.channel_id },
      user_id: { type: Schema.slack.types.user_id },
    },
    required: ["channel_id", "user_id"],
  },
});

export default SlackFunction(KosenStatusFunction, async ({ inputs, client }) => {
  const result = await client.apps.datastore.get({
    datastore: SettingsDatastore.name,
    id: "global",
  });
  if (!result.item) {
    await client.chat.postEphemeral({
      channel: inputs.channel_id,
      user: inputs.user_id,
      text: "⚠️ 先に「高専カウントダウン設定」を実行してください。",
    });
    return { outputs: {} };
  }
  const text = countdownMessage(String(result.item.exam_date)) ??
    "✅ 設定されている高専入試日は終了しています。";
  await client.chat.postEphemeral({ channel: inputs.channel_id, user: inputs.user_id, text });
  return { outputs: {} };
});
