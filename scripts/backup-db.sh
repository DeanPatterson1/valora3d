#!/usr/bin/env bash
# Encrypted logical backup of the Supabase database.
#
#   SUPABASE_DB_URL='postgres://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres' \
#     scripts/backup-db.sh [out-dir]
#
# Writes <out-dir>/<YYYY-MM-DD>.sql.gz.age (default out-dir: ./backups) and prints its path on the last line.
# Runs the same on a laptop and in .github/workflows/db-backup.yml. Needs Docker (the Supabase CLI runs pg_dump in a
# container of the matching Postgres version) and `age`.
#
# What is in it: `supabase db dump` three times, concatenated in the order Supabase documents for a restore:
#   roles.sql            custom roles (no passwords)
#   schema.sql           every non-Supabase-managed schema (public and its functions, triggers, RLS policies)
#   data.sql             COPY data for public AND auth/storage rows (auth.users, identities...), with
#                        `SET session_replication_role = replica` at its head
# The URL must be the SESSION pooler (port 5432): GitHub runners and most home networks are IPv4-only and the direct
# connection is IPv6-only unless the IPv4 add-on is on. The transaction pooler (6543) cannot run pg_dump.
#
# Env: SUPABASE_DB_URL (required) | SUPABASE_CLI (default "npx --yes supabase@latest") | AGE_RECIPIENTS_FILE |
#      BACKUP_DATE (default: today, UTC)
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
die() { echo "backup-db: $*" >&2; exit 1; }

[ -n "${SUPABASE_DB_URL:-}" ] || die "SUPABASE_DB_URL is not set (use the Supabase session pooler URL)"
recipients="${AGE_RECIPIENTS_FILE:-$root/infra/backup/age-recipients.txt}"
[ -f "$recipients" ] || die "no recipients file at $recipients"
# A real age public key is age1 + 58 bech32 characters; the placeholder lines in the repo are not.
grep -Eq '^age1[02-9ac-hj-np-z]{58}$' "$recipients" || die "$recipients has no real age public key yet (see the comments in it)"
grep -Eq '^age1REPLACE' "$recipients" && die "$recipients still has a placeholder line; replace or delete it"
command -v age >/dev/null || die "age is not installed (apt-get install age | brew install age | scoop install age)"

out_dir="${1:-$root/backups}"
date_utc="${BACKUP_DATE:-$(date -u +%Y-%m-%d)}"
[[ "$date_utc" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || die "BACKUP_DATE must be YYYY-MM-DD"
mkdir -p "$out_dir"

# Plaintext exists only inside this directory and is removed on every exit path.
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
read -r -a cli <<<"${SUPABASE_CLI:-npx --yes supabase@latest}"

echo "backup-db: dumping roles"
"${cli[@]}" db dump --db-url "$SUPABASE_DB_URL" -f "$work/roles.sql" --role-only
echo "backup-db: dumping schema"
"${cli[@]}" db dump --db-url "$SUPABASE_DB_URL" -f "$work/schema.sql"
echo "backup-db: dumping data"
"${cli[@]}" db dump --db-url "$SUPABASE_DB_URL" -f "$work/data.sql" --use-copy --data-only

cat "$work/roles.sql" "$work/schema.sql" "$work/data.sql" >"$work/dump.sql"
bytes="$(wc -c <"$work/dump.sql" | tr -d ' ')"
[ "$bytes" -gt 20000 ] || die "dump is only $bytes bytes: refusing to treat it as a backup"

# Sanity: every core table must be in the data section. A dump that silently lost a schema is worse than no dump.
while read -r table; do
  case "$table" in ''|'#'*) continue ;; esac
  schema="${table%%.*}"; name="${table#*.}"
  grep -Fq "COPY \"$schema\".\"$name\" " "$work/data.sql" || die "core table $table is missing from the dump"
done <"$root/infra/backup/core-tables.txt"
grep -Fq 'COPY "auth"."users" ' "$work/data.sql" || die "auth.users is missing from the dump (accounts would be lost)"

target="$out_dir/$date_utc.sql.gz.age"
gzip -9 -c "$work/dump.sql" | age -R "$recipients" -o "$target.tmp"
mv "$target.tmp" "$target"
echo "backup-db: $bytes bytes of SQL -> $(wc -c <"$target" | tr -d ' ') bytes encrypted"
echo "$target"
