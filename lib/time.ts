const JST_OFFSET_MS = 9 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

export type DateParts = { year: number; month: number; day: number };

export function parseDate(value: string): DateParts {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (!match) throw new Error("日付は YYYY-MM-DD 形式で入力してください。");
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const check = new Date(Date.UTC(year, month - 1, day));
  if (
    check.getUTCFullYear() !== year || check.getUTCMonth() !== month - 1 ||
    check.getUTCDate() !== day
  ) {
    throw new Error("存在しない日付です。");
  }
  return { year, month, day };
}

export function parseTime(value: string): { hour: number; minute: number } {
  const match = /^(\d{2}):(\d{2})$/.exec(value.trim());
  if (!match) throw new Error("時間は HH:MM 形式で入力してください。");
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) throw new Error("存在しない時間です。");
  return { hour, minute };
}

export function jstDateParts(now = new Date()): DateParts {
  const shifted = new Date(now.getTime() + JST_OFFSET_MS);
  return {
    year: shifted.getUTCFullYear(),
    month: shifted.getUTCMonth() + 1,
    day: shifted.getUTCDate(),
  };
}

export function dateKey(parts: DateParts): string {
  return `${parts.year}-${String(parts.month).padStart(2, "0")}-${
    String(parts.day).padStart(2, "0")
  }`;
}

export function jstDateTime(date: string, time: string): Date {
  const d = parseDate(date);
  const t = parseTime(time);
  return new Date(Date.UTC(d.year, d.month - 1, d.day, t.hour - 9, t.minute));
}

export function nextJstOccurrence(time: string, now = new Date()): Date {
  const today = jstDateParts(now);
  let candidate = jstDateTime(dateKey(today), time);
  if (candidate.getTime() <= now.getTime() + 30_000) {
    const nextDay = new Date(Date.UTC(today.year, today.month - 1, today.day) + DAY_MS);
    candidate = jstDateTime(
      dateKey({
        year: nextDay.getUTCFullYear(),
        month: nextDay.getUTCMonth() + 1,
        day: nextDay.getUTCDate(),
      }),
      time,
    );
  }
  return candidate;
}

export function daysUntil(examDate: string, now = new Date()): number {
  const exam = parseDate(examDate);
  const today = jstDateParts(now);
  const examUtc = Date.UTC(exam.year, exam.month - 1, exam.day);
  const todayUtc = Date.UTC(today.year, today.month - 1, today.day);
  return Math.round((examUtc - todayUtc) / DAY_MS);
}

export function formatJapaneseDate(date: string): string {
  const d = parseDate(date);
  return `${d.year}年${d.month}月${d.day}日`;
}
