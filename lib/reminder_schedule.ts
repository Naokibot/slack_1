import { reminderMessage } from "./messages.ts";

export const SCHEDULE_HORIZON_DAYS = 100;
export const MAX_PENDING_REMINDERS = 100;

export function insideScheduleHorizon(scheduledAt: number, now = Date.now()): boolean {
  const max = now + SCHEDULE_HORIZON_DAYS * 24 * 60 * 60 * 1000;
  return scheduledAt <= max;
}

export async function scheduleSlackMessage(
  client: {
    chat: {
      scheduleMessage: (args: Record<string, unknown>) => Promise<Record<string, unknown>>;
    };
  },
  item: {
    title: string;
    scheduled_at: number;
    scheduled_date: string;
    scheduled_time: string;
    channel_id: string;
  },
): Promise<string> {
  const response = await client.chat.scheduleMessage({
    channel: item.channel_id,
    text: reminderMessage(item.title, item.scheduled_date, item.scheduled_time),
    post_at: Math.floor(item.scheduled_at / 1000),
  });
  if (response.ok === false || typeof response.scheduled_message_id !== "string") {
    throw new Error(`Slackへの予約に失敗しました: ${String(response.error ?? "unknown_error")}`);
  }
  return response.scheduled_message_id;
}
