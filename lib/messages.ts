import { daysUntil, formatJapaneseDate } from "./time.ts";

export function countdownMessage(examDate: string, now = new Date()): string | null {
  const days = daysUntil(examDate, now);
  if (days < 0) return null;
  if (days === 0) {
    return "🎓 *高専入試当日です*\n\n今日は高専入試の日です。\n落ち着いて、これまで勉強してきたことを出してきてください。";
  }
  if (days === 1) {
    return `🔥 *高専入試まであと1日*\n\n試験日：${formatJapaneseDate(examDate)}\n\nいよいよ明日です。\n忘れ物と受験会場・時間を確認しておこう。`;
  }
  return `📚 *高専入試まであと${days}日*\n\n試験日：${formatJapaneseDate(examDate)}\n\n今日も1日、少しずつ進めよう。`;
}

export function reminderMessage(title: string, date: string, time: string): string {
  const formattedDate = date.replace(/^(\d{4})-(\d{2})-(\d{2})$/, "$1年$2月$3日");
  return `⏰ *リマインダー*\n\n${title}\n\n📅 ${formattedDate}\n🕖 ${time}`;
}
