#!/usr/bin/env node
// Retention for the database backups in R2: keep the last 30 daily backups and one backup per month for the last
// 12 months (the earliest one in each month, normally the 1st); delete the rest.
//
//   node scripts/backup-prune.mjs [--dry-run]
//
// Env: R2_ACCOUNT_ID, R2_BACKUP_BUCKET (default valora3d-backups), AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (the R2
// backup token), and the `aws` CLI. Only keys shaped exactly backups/db/YYYY/MM/DD.sql.gz.age are ever considered;
// anything else in the bucket is left alone. The newest backup is never deleted, and an empty or unparseable listing
// deletes nothing.
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

export const DAILY_KEEP = 30;
export const MONTHLY_KEEP = 12;
const KEY = /^backups\/db\/(\d{4})\/(\d{2})\/(\d{2})\.sql\.gz\.age$/;

/** Parses a backup key into its UTC date, or null when it is not one of ours (or not a real date). */
export function keyDate(key) {
  const m = KEY.exec(key);
  if (!m) return null;
  const [, y, mo, d] = m.map(Number);
  const date = new Date(Date.UTC(y, mo - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === mo - 1 && date.getUTCDate() === d ? date : null;
}

/**
 * Which keys to delete. Pure: `today` is a Date, `keys` the listing.
 * Keep = backups from the last DAILY_KEEP days (today included) + the earliest backup of each of the last
 * MONTHLY_KEEP calendar months (this month included) + the newest backup overall.
 */
export function selectPrune(keys, today) {
  const dated = keys.map((key) => ({ key, date: keyDate(key) })).filter((x) => x.date);
  if (dated.length === 0) return [];
  const dayMs = 86_400_000;
  const todayUtc = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const keep = new Set();
  for (const { key, date } of dated) {
    if (todayUtc - date.getTime() < DAILY_KEEP * dayMs) keep.add(key);
  }
  const monthIndex = (d) => d.getUTCFullYear() * 12 + d.getUTCMonth();
  const thisMonth = monthIndex(today);
  const firstOfMonth = new Map();
  for (const { key, date } of dated) {
    const m = monthIndex(date);
    if (thisMonth - m >= MONTHLY_KEEP || m > thisMonth) continue;
    const best = firstOfMonth.get(m);
    if (!best || date < best.date) firstOfMonth.set(m, { key, date });
  }
  for (const { key } of firstOfMonth.values()) keep.add(key);
  keep.add(dated.reduce((a, b) => (b.date > a.date ? b : a)).key);
  return dated.map((x) => x.key).filter((key) => !keep.has(key)).sort();
}

function aws(args, env) {
  return execFileSync("aws", args, { encoding: "utf8", env, maxBuffer: 64 * 1024 * 1024 });
}

function main() {
  const dryRun = process.argv.includes("--dry-run");
  const account = process.env.R2_ACCOUNT_ID?.trim();
  const bucket = process.env.R2_BACKUP_BUCKET?.trim() || "valora3d-backups";
  if (!account || !/^[a-f0-9]{32}$/i.test(account)) throw new Error("R2_ACCOUNT_ID must be the 32-character Cloudflare account id");
  const env = {
    ...process.env,
    AWS_DEFAULT_REGION: "auto",
    AWS_REQUEST_CHECKSUM_CALCULATION: "when_required",
    AWS_RESPONSE_CHECKSUM_VALIDATION: "when_required",
  };
  const endpoint = `https://${account}.r2.cloudflarestorage.com`;
  const listing = JSON.parse(
    aws(["s3api", "list-objects-v2", "--endpoint-url", endpoint, "--bucket", bucket, "--prefix", "backups/db/", "--query", "Contents[].Key", "--output", "json"], env) || "null",
  );
  const keys = Array.isArray(listing) ? listing : [];
  const doomed = selectPrune(keys, new Date());
  console.log(`backup-prune: ${keys.length} objects listed, ${doomed.length} to delete${dryRun ? " (dry run)" : ""}`);
  for (const key of doomed) {
    console.log(`  ${dryRun ? "would delete" : "delete"} ${key}`);
    if (!dryRun) aws(["s3api", "delete-object", "--endpoint-url", endpoint, "--bucket", bucket, "--key", key], env);
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main();
