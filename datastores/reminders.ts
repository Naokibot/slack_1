import { DefineDatastore, Schema } from "deno-slack-sdk/mod.ts";

const RemindersDatastore = DefineDatastore({
  name: "reminders",
  primary_key: "id",
  attributes: {
    id: { type: Schema.types.string },
    title: { type: Schema.types.string },
    scheduled_at: { type: Schema.types.number },
    scheduled_date: { type: Schema.types.string },
    scheduled_time: { type: Schema.types.string },
    channel_id: { type: Schema.slack.types.channel_id },
    user_id: { type: Schema.slack.types.user_id },
    status: { type: Schema.types.string },
    revision: { type: Schema.types.number },
    schedule_state: { type: Schema.types.string },
    scheduled_message_id: { type: Schema.types.string },
    created_at: { type: Schema.types.number },
    updated_at: { type: Schema.types.number },
    notified_at: { type: Schema.types.number },
  },
});

export default RemindersDatastore;
