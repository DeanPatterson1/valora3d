#!/usr/bin/env node
// Applies the R2 bucket configuration kept in infra/r2/ (CORS, lifecycle, optional backup lock) with wrangler.
//
//   node scripts/r2-apply.mjs                    # PRINTS the wrangler commands it would run (default, changes nothing)
//   node scripts/r2-apply.mjs --apply            # runs them against the real buckets
//   node scripts/r2-apply.mjs --only uploads     # or: backups
//   node scripts/r2-apply.mjs --include-localhost --apply   # adds http://localhost:3000 to the CORS origins (dev bucket only)
//   node scripts/r2-apply.mjs --lock-backups --apply        # also add a 7-day object lock to the backup bucket
//
// Env: R2_BUCKET (default valora3d-uploads), R2_BACKUP_BUCKET (default valora3d-backups); for --apply also
// CLOUDFLARE_API_TOKEN (permission: Workers R2 Storage: Edit) and CLOUDFLARE_ACCOUNT_ID.
// `cors set` and `lifecycle set` REPLACE the bucket's whole rule list, so this file set is the source of truth.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

export const WRANGLER = "wrangler@4.129.0";
const infra = (name) => fileURLToPath(new URL(`../infra/r2/${name}`, import.meta.url));

/** The wrangler argument lists to run, in order. Pure. */
export function plan({ uploads, backups, only, includeLocalhost, lockBackups, corsFile, corsFileWithLocalhost }) {
  const steps = [];
  if (only !== "backups") {
    steps.push({ label: `CORS on ${uploads}`, args: ["r2", "bucket", "cors", "set", uploads, "--file", includeLocalhost ? corsFileWithLocalhost : corsFile, "--force"] });
    steps.push({ label: `lifecycle on ${uploads}`, args: ["r2", "bucket", "lifecycle", "set", uploads, "--file", infra("uploads.lifecycle.json"), "--force"] });
  }
  if (only !== "uploads") {
    steps.push({ label: `lifecycle on ${backups} (abort multipart only; retention is scripts/backup-prune.mjs)`, args: ["r2", "bucket", "lifecycle", "set", backups, "--file", infra("backups.lifecycle.json"), "--force"] });
    if (lockBackups) steps.push({ label: `7-day object lock on ${backups}`, args: ["r2", "bucket", "lock", "add", backups, "retain-7d", "", "--retention-days", "7", "--force"] });
  }
  return steps;
}

function main() {
  const argv = process.argv.slice(2);
  const flag = (name) => argv.includes(name);
  const only = argv.includes("--only") ? argv[argv.indexOf("--only") + 1] : undefined;
  if (only && !["uploads", "backups"].includes(only)) throw new Error("--only takes uploads or backups");
  const uploads = process.env.R2_BUCKET?.trim() || "valora3d-uploads";
  const backups = process.env.R2_BACKUP_BUCKET?.trim() || "valora3d-backups";
  for (const b of [uploads, backups]) if (!/^[a-z0-9][a-z0-9-]{2,62}$/.test(b)) throw new Error(`not a bucket name: ${b}`);

  const dir = mkdtempSync(join(tmpdir(), "r2-apply-"));
  try {
    const cors = JSON.parse(readFileSync(infra("uploads.cors.json"), "utf8"));
    const withLocal = structuredClone(cors);
    withLocal.rules[0].allowed.origins.push("http://localhost:3000");
    const corsFileWithLocalhost = join(dir, "cors-with-localhost.json");
    writeFileSync(corsFileWithLocalhost, JSON.stringify(withLocal, null, 2));
    const steps = plan({ uploads, backups, only, includeLocalhost: flag("--include-localhost"), lockBackups: flag("--lock-backups"), corsFile: infra("uploads.cors.json"), corsFileWithLocalhost });

    const apply = flag("--apply");
    if (apply && (!process.env.CLOUDFLARE_API_TOKEN || !process.env.CLOUDFLARE_ACCOUNT_ID)) {
      throw new Error("--apply needs CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID");
    }
    console.log(apply ? "r2-apply: APPLYING to the real buckets" : "r2-apply: dry run (add --apply to change anything)");
    for (const step of steps) {
      console.log(`\n# ${step.label}\nnpx ${WRANGLER} ${step.args.map((a) => (a === "" ? '""' : a)).join(" ")}`);
      if (apply) execFileSync("npx", ["--yes", WRANGLER, ...step.args], { stdio: "inherit", shell: process.platform === "win32" });
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main();
