import { DefineDatastore, Schema } from "deno-slack-sdk/mod.ts";

const SettingsDatastore = DefineDatastore({
  name: "settings",
  primary_key: "id",
  attributes: {
    id: { type: Schema.types.string },
    exam_date: { type: Schema.types.string },
    notify_time: { type: Schema.types.string },
    channel_id: { type: Schema.slack.types.channel_id },
    owner_user_id: { type: Schema.slack.types.user_id },
    revision: { type: Schema.types.number },
    daily_trigger_id: { type: Schema.types.string },
    last_countdown_date: { type: Schema.types.string },
    updated_at: { type: Schema.types.number },
  },
});

export default SettingsDatastore;
