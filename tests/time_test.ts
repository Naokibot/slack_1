import { assertEquals, assertThrows } from "https://deno.land/std@0.224.0/assert/mod.ts";
import { countdownMessage } from "../lib/messages.ts";
import { daysUntil, jstDateTime, nextJstOccurrence, parseDate, parseTime } from "../lib/time.ts";

Deno.test("2026-08-14から2027-02-14までは184日", () => {
  const now = new Date("2026-08-14T00:00:00+09:00");
  assertEquals(daysUntil("2027-02-14", now), 184);
});

Deno.test("前日と当日のメッセージを切り替える", () => {
  const before = countdownMessage("2027-02-14", new Date("2027-02-13T08:00:00+09:00"));
  const today = countdownMessage("2027-02-14", new Date("2027-02-14T08:00:00+09:00"));
  assertEquals(before?.includes("あと1日"), true);
  assertEquals(today?.includes("入試当日"), true);
});

Deno.test("試験終了後はカウントダウンしない", () => {
  assertEquals(
    countdownMessage("2027-02-14", new Date("2027-02-15T08:00:00+09:00")),
    null,
  );
});

Deno.test("JST日時をUTCへ正しく変換する", () => {
  assertEquals(
    jstDateTime("2026-08-20", "19:00").toISOString(),
    "2026-08-20T10:00:00.000Z",
  );
});

Deno.test("次回通知時刻を求める", () => {
  const next = nextJstOccurrence("07:00", new Date("2026-08-14T06:00:00+09:00"));
  assertEquals(next.toISOString(), "2026-08-13T22:00:00.000Z");
});

Deno.test("不正な日付・時刻を拒否する", () => {
  assertThrows(() => parseDate("2026-02-30"));
  assertThrows(() => parseTime("24:00"));
});
