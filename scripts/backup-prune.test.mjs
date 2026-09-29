import assert from "node:assert/strict";
import { test } from "node:test";
import { keyDate, selectPrune } from "./backup-prune.mjs";

const key = (iso) => `backups/db/${iso.slice(0, 4)}/${iso.slice(5, 7)}/${iso.slice(8, 10)}.sql.gz.age`;
const daysBack = (from, n) => new Date(from.getTime() - n * 86_400_000).toISOString().slice(0, 10);
const TODAY = new Date(Date.UTC(2026, 8, 29)); // 2026-09-29

test("keyDate accepts our keys only", () => {
  assert.equal(keyDate("backups/db/2026/09/29.sql.gz.age")?.toISOString().slice(0, 10), "2026-09-29");
  for (const bad of ["backups/db/2026/13/01.sql.gz.age", "backups/db/2026/02/30.sql.gz.age", "backups/db/2026/09/29.sql.gz", "x/backups/db/2026/09/29.sql.gz.age", "backups/db/2026/09/29.sql.gz.age.tmp", ""]) {
    assert.equal(keyDate(bad), null, bad);
  }
});

test("keeps 30 dailies and one per month for 12 months, deletes the rest", () => {
  const keys = Array.from({ length: 800 }, (_, i) => key(daysBack(TODAY, i)));
  const doomed = new Set(selectPrune(keys, TODAY));
  const kept = keys.filter((k) => !doomed.has(k));
  // The 30 newest days survive.
  for (let i = 0; i < 30; i++) assert.ok(kept.includes(key(daysBack(TODAY, i))), `daily ${i}`);
  assert.ok(!kept.includes(key(daysBack(TODAY, 30))) || daysBack(TODAY, 30).endsWith("-01") || daysBack(TODAY, 30) === "2026-08-30", "day 31 is monthly-or-gone");
  // Exactly one older-than-30-days backup per month, the 1st, for Oct 2025 .. Sep 2026.
  const monthly = kept.filter((k) => !Array.from({ length: 30 }, (_, i) => key(daysBack(TODAY, i))).includes(k));
  assert.ok(monthly.length <= 12, `${monthly.length} monthlies`);
  for (const m of ["2025-10-01", "2025-11-01", "2026-01-01", "2026-06-01", "2026-08-01"]) assert.ok(kept.includes(key(m)), m);
  // Older than 12 months is gone.
  assert.ok(doomed.has(key("2025-08-01")));
  assert.ok(doomed.has(key("2025-01-01")));
  // Mid-month backups older than 30 days are gone.
  assert.ok(doomed.has(key("2026-07-15")));
});

test("a month without a 1st keeps its earliest backup", () => {
  const keys = [key("2026-05-03"), key("2026-05-20"), key(daysBack(TODAY, 0))];
  assert.deepEqual(selectPrune(keys, TODAY), [key("2026-05-20")]);
});

test("never deletes the newest backup, even if it is old (the job has been failing)", () => {
  const keys = [key("2024-01-01"), key("2024-01-02")];
  assert.deepEqual(selectPrune(keys, TODAY), [key("2024-01-01")]);
});

test("empty or foreign listings delete nothing", () => {
  assert.deepEqual(selectPrune([], TODAY), []);
  assert.deepEqual(selectPrune(["backups/db/notes.txt", "uploads/u/x.glb", "backups/db/2026/09/29.sql"], TODAY), []);
});

test("future-dated keys are not treated as a monthly slot", () => {
  const keys = [key("2027-03-01"), key("2026-09-29")];
  assert.deepEqual(selectPrune(keys, TODAY), []);
});
