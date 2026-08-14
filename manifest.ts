import { Manifest } from "deno-slack-sdk/mod.ts";

import SettingsDatastore from "./datastores/settings.ts";
import RemindersDatastore from "./datastores/reminders.ts";
import {
  KosenDailyWorkflow,
  KosenSettingsWorkflow,
  KosenStatusWorkflow,
  ReminderAddWorkflow,
  ReminderDeleteWorkflow,
  ReminderEditWorkflow,
  ReminderListWorkflow,
} from "./workflows.ts";

export default Manifest({
  name: "KOSEN Assistant",
  description: "高専入試カウントダウンと予定リマインダー",
  workflows: [
    KosenDailyWorkflow,
    KosenSettingsWorkflow,
    KosenStatusWorkflow,
    ReminderAddWorkflow,
    ReminderListWorkflow,
    ReminderEditWorkflow,
    ReminderDeleteWorkflow,
  ],
  datastores: [SettingsDatastore, RemindersDatastore],
  botScopes: [
    "commands",
    "chat:write",
    "datastore:read",
    "datastore:write",
    "triggers:read",
    "triggers:write",
  ],
});
