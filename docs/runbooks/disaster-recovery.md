# Disaster recovery runbook

Owner: the account owner. Last reviewed: 2026-09-29. Review it every quarter (checklist at the end) and after any change to a provider, a secret or the schema.

The site is a static-ish Next.js app on Cloudflare Workers, Postgres + Auth on Supabase, files on R2, GPUs on RunPod, money on Paddle, mail on Resend. Only the database and a few settings are irreplaceable. Everything else is rebuilt from git, re-rendered, or re-uploaded.

## 1. Targets

| What | RPO (data you can lose) | RTO (time to be back) | How |
|---|---|---|---|
| Database (accounts, projects, credit ledger, billing rows, jobs, shares) | 24 h (nightly dump). Drops to about 1 h only if you buy Supabase PITR. | 2 h | Section 4 |
| Code | 0 once pushed | 30 min | GitHub `DeanPatterson1/valora3d` (private), `worker/runpod` branch of the renderer |
| Uploaded models (`u/<user>/...` in R2) | Not backed up. Users hold the originals. | n/a | Users re-upload. Say so in an incident message. |
| Render outputs (`r/<user>/<job>/...` in R2) | Not backed up. Re-renderable, and users are told to download. | n/a | Refund or re-render on request (Admin -> Renders -> Retry / Refund) |
| Worker secrets | 0, if you keep them in the password manager (section 5) | 30 min | `wrangler secret put` |
| Billing truth | 0 | hours | Paddle keeps every transaction and can replay webhooks (section 4, step 9) |

These are placeholder targets. Tighten them when revenue justifies it: Supabase Pro plus PITR gets the database to about 1 h RPO.

## 2. What is backed up where

| Data | Where the copy lives | Notes |
|---|---|---|
| Postgres: `public` tables and functions, RLS policies, **auth.users and identities**, storage metadata | `backups/db/YYYY/MM/DD.sql.gz.age` in the R2 bucket `valora3d-backups` (its own bucket, its own API token) | Made nightly at 02:17 UTC by `.github/workflows/db-backup.yml`. Encrypted with age: the owner's offline key and a CI test key can decrypt. Retention: 30 daily plus 12 monthly (`scripts/backup-prune.mjs`). |
| Same database, second layer | Supabase's own daily backups | Pro plan only (7 days). Free has none. **Use Pro before taking money.** |
| Proof that the backup restores | `.github/workflows/db-restore-verify.yml`, Sundays 04:41 UTC | Restores the newest file into a throwaway Postgres and compares row counts. It also fails when the newest backup is more than 2 days old, so a silently dead nightly job cannot hide. |
| R2 `valora3d-uploads` (models and render outputs) | Nowhere. **R2 has no object versioning**, so a bad purge or a leaked token deletes for good. | Mitigations below. |
| Code, migrations, email templates (`supabase/templates`), Wrangler config, workflows | GitHub | `wrangler.jsonc` holds cron, routes and the rate-limit binding. |
| Cloudflare DNS, Access policies, Turnstile widget | Cloudflare only | Export DNS once a quarter (Dashboard -> DNS -> Records -> Export) and keep the file in the password manager. Access bypass paths are listed in `apps/web/README.md`. |
| Supabase dashboard settings: auth providers (Google), SMTP, CAPTCHA, URL configuration, email confirmation | Supabase only, not in the dump | Rebuild by hand (section 4, step 6). Screenshot them at each quarterly review. |
| Renderer worker image and endpoint config | Renderer repo (`worker/runpod` branch) and the container registry | The RunPod endpoint settings (GPU type, max workers, env) are only in RunPod's console: screenshot them. |
| Paddle products, prices, notification destination | Paddle | Price ids live in Worker env. Note them in the password manager. |

### R2 objects: protect what has no backup

1. **Least privilege.** The app's R2 token is scoped to `valora3d-uploads` only, Object Read and Write. It must not be able to touch `valora3d-backups`. Delete permission exists, so the token is the risk: rotate it on any suspicion (section 5).
2. **Lifecycle as code.** `infra/r2/` holds the CORS rule and the lifecycle rule (abort incomplete multipart uploads after 1 day). Apply with `node scripts/r2-apply.mjs` (prints the commands) and `--apply` (runs them). Never applied automatically.
3. **Optional, when it is worth it.** R2 cannot version objects. If losing user uploads becomes unacceptable, add a second bucket in another Cloudflare account or a different provider and copy new objects with a scheduled `rclone sync --immutable` or R2's Sippy/Super Slurper migration. Do not enable it before there are paying users: users still hold their originals, and outputs are re-renderable.
4. **Backup bucket lock.** `node scripts/r2-apply.mjs --only backups --lock-backups --apply` adds a 7-day object lock, so even a stolen backup token cannot delete last week's dumps. A locked key cannot be overwritten either, so re-run a failed backup the next day instead of twice on the same day.

## 3. Set up backups (owner, once)

1. Push the repo to the private GitHub remote (done: `DeanPatterson1/valora3d`).
2. **Supabase**: upgrade to Pro. Dashboard -> Connect -> **Session pooler** connection string (port 5432; the direct connection is IPv6-only and GitHub runners are IPv4). Put the database password in the string. This is `SUPABASE_DB_URL`.
3. **R2**: create the bucket `valora3d-backups` (Standard storage, no public access, no custom domain). Create an API token: Object Read and Write, **scoped to that bucket only**. Note the access key id and secret.
4. **age keys** (on your PC; install with `winget install FiloSottile.age`):
   ```
   age-keygen -o valora3d-backup-owner.key
   age-keygen -o valora3d-backup-ci.key
   ```
   Each prints `Public key: age1...`. Edit `infra/backup/age-recipients.txt`: replace the two placeholder lines with those two public keys, commit.
   - `valora3d-backup-owner.key` is the disaster key. Store it offline: password manager plus a printed copy in a safe place. Losing it and the CI key means the backups are unreadable.
   - `valora3d-backup-ci.key`: paste its full contents into the GitHub secret `AGE_VERIFY_IDENTITY`, then delete the local file. It only lets the weekly job test-restore.
5. GitHub -> repo -> Settings -> Secrets and variables -> Actions:
   - Secrets: `SUPABASE_DB_URL`, `R2_ACCOUNT_ID`, `R2_BACKUP_ACCESS_KEY_ID`, `R2_BACKUP_SECRET_ACCESS_KEY`, `AGE_VERIFY_IDENTITY`.
   - Variable (optional): `R2_BACKUP_BUCKET` (default `valora3d-backups`).
6. Actions -> **DB backup** -> Run workflow. It must finish green and the summary shows the uploaded key. Then Actions -> **DB restore verify** -> Run workflow: green means the file decrypts and every core table's row count matches.
7. If the verify job fails on its first run, read the printed errors before assuming the backup is bad: the throwaway image is a bare `supabase/postgres`, and a table that depends on something GoTrue creates at runtime shows up there. Fix the job or the core-table list (`infra/backup/core-tables.txt`), and do the strict drill in section 7 once.
8. GitHub emails you when a scheduled run fails. Keep that notification on.

Run the same thing locally when you want a fresh dump: `SUPABASE_DB_URL=... scripts/backup-db.sh` (needs Docker and `age`).

## 4. Restore the database into a new Supabase project

Use this for a real disaster (project lost, corrupted, or compromised) and for the quarterly drill (section 7). Budget: 2 hours.

1. **Get the file.** Cloudflare -> R2 -> `valora3d-backups` -> `backups/db/YYYY/MM/` -> download the newest `DD.sql.gz.age` (or the one from just before the incident).
2. **Create the target.** Supabase -> New project, **same region and Postgres major version (17)**. For a drill use a scratch project. For a real disaster this is the new production project. Copy its session pooler URL (port 5432) as `TARGET_URL`.
3. **Install tools** (Windows: `winget install FiloSottile.age PostgreSQL.PostgreSQL.17`; use WSL or Git Bash for the script).
4. **Restore.** From the repo root:
   ```
   AGE_IDENTITY_FILE=/path/to/valora3d-backup-owner.key \
     scripts/restore-db.sh ~/Downloads/2026-09-29.sql.gz.age "$TARGET_URL" --verify
   ```
   It asks you to type the target host, decrypts, and replays roles, schema and data in one transaction (all or nothing). `--verify` then compares every core table's row count with the dump. The dump is Supabase's documented format: roles, schema, then data with triggers disabled, so credit and event triggers do not fire twice.
   - If it stops with an error, the transaction rolled back and the project is untouched: fix the cause and rerun. Common ones: a Postgres extension not enabled on the new project (Dashboard -> Database -> Extensions), or the project is not empty (use a fresh one).
5. **Apply migrations newer than the backup** (only when the app moved on since the dump): `cd apps/web && supabase link --project-ref <ref> && supabase db push`.
6. **Re-create dashboard settings** (not in any dump): Authentication -> Providers -> Email (confirm email on) and Google (client id and secret); URL configuration (site URL `https://valora3d.com`, redirect `https://valora3d.com/auth/callback`); Attack Protection -> CAPTCHA -> Turnstile secret; SMTP if used; paste the email templates from `apps/web/supabase/templates/` (Authentication -> Emails).
7. **Point the app at the new project.** New values: `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` (build-time, so rebuild) and `SUPABASE_SERVICE_ROLE_KEY` (`wrangler secret put`). Then `cd apps/web && npm run deploy`. Anyone signed in has to sign in again if the JWT secret differs from the old project.
8. **Smoke check**: sign in, open a project, open the studio, check Admin -> Overview numbers against the last digest email. Sign-ups: `signups_enabled` must be on.
9. **Paddle catch-up** (only if the restore point is before the incident): Paddle -> Developer tools -> Notifications -> the destination -> Logs, resend every event after the backup time. The webhook is idempotent on the event id and the ledger reference, so replaying cannot double-grant credits. Any render that finished after the backup and lost its row: refund or re-render on request.
10. **Tell users** what was lost (up to 24 hours of changes) and thank them for re-uploading anything missing.

Losing the database but not the project? First try Supabase's own backups (Dashboard -> Database -> Backups; Pro plan) before touching the R2 dump.

## 5. Rotating every secret

Values live in Cloudflare Worker secrets (`cd apps/web && npx wrangler secret put NAME`), GitHub Actions secrets, or a provider console. Build-time values (`NEXT_PUBLIC_*`) need a rebuild and deploy. After every rotation: `npm run deploy`, then run the smoke check (sign in, upload, render, buy in sandbox).

| Secret | Where it lives | How to rotate | Watch out |
|---|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | Worker secret | Supabase -> Project Settings -> API keys -> create a new secret key, `wrangler secret put`, deploy, then revoke the old key | Server routes fail (500) between revoking and deploying: do it in that order. Revoke immediately if it ever appears in chat, logs or git. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Build-time | Same page. Public by design; RLS is the protection. Rotate only for a JWT-secret change. | Rebuild required. |
| Supabase database password | Supabase; inside `SUPABASE_DB_URL` (GitHub) | Project Settings -> Database -> Reset password, then update the GitHub secret `SUPABASE_DB_URL` | The nightly backup fails until updated. |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Worker secrets | Cloudflare -> R2 -> Manage API tokens -> create a new token scoped to `valora3d-uploads`, put both values, deploy, delete the old token | Presigned URLs already handed out die with the old key; users retry. |
| `R2_ACCOUNT_ID` | Worker secret, GitHub secret | Not secret in the cryptographic sense; it also builds the CSP R2 host | Change only when moving accounts. |
| `R2_BACKUP_ACCESS_KEY_ID`, `R2_BACKUP_SECRET_ACCESS_KEY` | GitHub secrets | New token scoped to `valora3d-backups`, update both secrets, delete the old token, run **DB backup** manually | The app never has this token. |
| age keys | Offline (owner), GitHub `AGE_VERIFY_IDENTITY`, public halves in `infra/backup/age-recipients.txt` | Generate a new pair, replace the public line in the recipients file, commit, run **DB backup**. Old backups stay readable only with the old private key: keep it until they age out (13 months). | Never delete an old owner key while backups made for it exist. |
| `PADDLE_API_KEY` | Worker secret | Paddle -> Developer tools -> Authentication -> new API key, deploy, revoke the old | Manage billing and plan changes fail in between. |
| `PADDLE_WEBHOOK_SECRET` | Worker secret | Paddle -> Notifications -> destination -> new secret; set both the secret and Paddle in the same minute | Events in that gap are retried by Paddle for about 3 days; use Logs -> Resend. |
| `NEXT_PUBLIC_PADDLE_CLIENT_TOKEN`, `NEXT_PUBLIC_PADDLE_ENV`, `PADDLE_PRICE_*`, `PADDLE_PROMO_PRICE_IDS` | Build-time | Paddle console; rebuild | Client token is public. Sandbox and live ids differ. |
| `CHECKOUT_SIGNING_SECRET` (`_PREVIOUS`) | Worker secret | `openssl rand -hex 32`. Set the NEW value as `CHECKOUT_SIGNING_SECRET` and the OLD as `CHECKOUT_SIGNING_SECRET_PREVIOUS`, deploy, wait 7 days, remove `_PREVIOUS` | Skipping the window strands checkouts opened before the switch. |
| `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID` | Worker secrets | RunPod -> Settings -> API keys -> new key, deploy, delete the old. The endpoint id changes only if you recreate the endpoint. | Set a spend cap on the new key's account. |
| Renderer env inside the RunPod endpoint (`ANTHROPIC_API_KEY`, R2 credentials if the worker has its own) | RunPod endpoint settings | New key in the provider, update the endpoint's environment, Save (workers restart) | Use a dedicated, low-cap Anthropic key: it sits next to code that parses untrusted models. |
| `RESEND_API_KEY` | Worker secret | Resend -> API keys -> new key with sending access, deploy, delete old | No mail until deployed. |
| `RESEND_WEBHOOK_SECRET` | Worker secret | Resend -> Webhooks -> signing secret, update both | Bounce handling is closed until both match. |
| `EMAIL_UNSUBSCRIBE_SECRET` | Worker secret | New 32+ character random value | Links in mail already sent stop working. Leave it unset only if you accept it derives from the service-role key. |
| `CRON_SECRET` | Worker secret | New random value (32+ characters). The cron trigger reads the same secret. | The sweep is closed until deployed; renders finish via webhook meanwhile. |
| `OWNER_ALERT_EMAIL` | Worker secret | Just the address | |
| Turnstile secret | **Supabase** (Attack Protection), never in the app | Cloudflare -> Turnstile -> widget -> rotate secret, paste into Supabase | Sign-ups and log-ins fail if the two drift. |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, `NEXT_PUBLIC_CF_ANALYTICS_TOKEN` | Build-time | Public values | Rebuild. |
| Google OAuth client secret | Supabase (Auth -> Providers -> Google) and Google Cloud | Google Cloud Console -> Credentials -> reset secret, paste into Supabase | Google sign-in fails between the two steps. |
| Cloudflare API token used to deploy (`CLOUDFLARE_API_TOKEN`) | Your machine or CI | Cloudflare -> My Profile -> API Tokens -> roll | Also used by `scripts/r2-apply.mjs`. |
| GitHub | Your account | Enable 2FA (passkey), review Settings -> Deploy keys and Actions secrets | A GitHub takeover exposes the database URL and the CI age key. |

If a secret leaked: rotate it first, then check the provider's logs for use, then write a note in the incident log. For the service-role key and database password, assume everything readable through them was read.

## 6. When a provider is down

Feature flags are the pressure valve. Admin -> Flags (`/admin/flags`), takes effect within about 30 seconds on every Worker: `renders_enabled`, `finals_enabled`, `signups_enabled`, `sharing_enabled`, `checkout_enabled`. Turning a switch off shows visitors a plain "paused" state instead of failing. If the admin console is unreachable (Supabase down), flags cannot change and, by design, read as **on** because a dead database already blocks those actions. When Supabase is back and you need to force one off from its dashboard, SQL editor:

```sql
update public.feature_flags set enabled = false where key = 'renders_enabled';
```

| Down | What users see | What to do |
|---|---|---|
| **Cloudflare** (Workers, DNS, R2) | The whole site is unreachable. | Nothing on your side helps. Watch cloudflarestatus.com. Post on your status channel or social profile. Nothing is lost: the database and Paddle are elsewhere. Afterwards check Paddle -> Notifications -> Logs for failed webhook deliveries and resend them. |
| **Supabase** | Sign-in, projects and the studio fail. Public marketing pages still load. Paddle webhooks fail and are retried by Paddle for about 3 days. | Watch status.supabase.com. Do not restore into a new project for an outage under about 2 hours. Longer, or if the project is gone: section 4. Set `checkout_enabled` off first if you can reach the admin console, so nobody pays into a site that cannot credit them. Afterwards resend failed Paddle events. |
| **RunPod** | Renders queue, then fail and are refunded automatically by the sweep. | Turn `renders_enabled` off so nobody queues more (they get a clear "paused" message and no credits move). Check RunPod status and your endpoint's worker logs. Turn it back on and Admin -> Renders -> Retry the failed jobs. If it is your endpoint config, not RunPod, see the worker README section 6. |
| **Paddle** | Checkout fails to open; portal links fail. Existing credits and plans keep working. | Turn `checkout_enabled` off so buttons say "unavailable" rather than erroring. Nothing is lost: once Paddle is back, deliveries resume. Never grant credits by hand for a payment you cannot see in Paddle. |
| **Resend** | Render-ready, lifecycle and owner mail stop. Sign-up confirmation goes through Supabase Auth's own SMTP, so it may still work. | Nothing breaks. Renders still finish and show in the app. Use the daily digest at 07:00 UTC as your health signal: if it does not arrive, check Resend. |
| **Anthropic** (the director in the worker) | Renders fail at the planning step. | Same as RunPod: pause renders, retry failed jobs later. |
| **GitHub** | Cannot push or run backups. | Production keeps running. Nightly backups skip; the weekly verify job flags a stale backup. Run `scripts/backup-db.sh` locally if the outage spans days. |

Incident log: write down times, what you turned off, what users were told, and any manual refunds (Admin -> Audit already records the admin actions).

## 7. Owner checklist: test a restore every quarter

Put a recurring calendar event: first Monday of January, April, July, October. 60 to 90 minutes.

1. Open Actions -> **DB restore verify**: the last run is green and less than 8 days old. Open a recent **DB backup** run: 7 consecutive nights green.
2. Download the newest backup from R2 with your own login (proves the bucket and the file are reachable without CI).
3. Create a scratch Supabase project (free is fine for a drill; delete it after).
4. Decrypt and restore with your **offline owner key**, strictly and with verification (section 4, steps 1 to 4). The command must finish with `restore-db: verified`.
5. In the scratch project: Table Editor -> `profiles` shows your account; Authentication -> Users lists the same number of users as production (rounded to the night the dump was taken).
6. Delete the scratch project and the downloaded file. Confirm `valora3d-backup-owner.key` is where you expect it (open the password manager entry and the printed copy).
7. Retention check: R2 -> `valora3d-backups/backups/db/` holds about 30 recent days plus one file per past month.
8. Secrets: open section 5 and rotate anything older than 12 months, plus anything a former helper could still see. Confirm no secret is in git: `git log -p -S "sb_secret_"` returns nothing.
9. Skim the provider list in section 6: are all the providers still the ones you use? Is a status page bookmarked for each?
10. Update "Last reviewed" at the top and commit.

Done means: strict restore verified, the offline key found, no stale secrets.
