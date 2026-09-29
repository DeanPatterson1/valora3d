#!/usr/bin/env bash
# Restore a backup made by scripts/backup-db.sh into a database.
#
#   AGE_IDENTITY_FILE=valora3d-backup-owner.key \
#     scripts/restore-db.sh <backup.sql.gz.age | dump.sql.gz | dump.sql> <target-db-url> [--verify] [--lenient] [--yes]
#
# Target: a FRESH Supabase project (Dashboard -> New project, same region), session pooler URL on port 5432, or any
# Postgres built from the supabase/postgres image. Never point this at the live production database: it replays
# CREATE and COPY statements and would fail or double-load.
#
#   --verify   after the restore, compare each core table's row count (infra/backup/core-tables.txt) with the count
#              inside the dump; exit 1 on any difference. Also reports auth.users.
#   --lenient  keep going past errors (no single transaction). Used by the weekly test restore into a bare
#              supabase/postgres container, whose auth schema is older than a real project's. A real restore is strict:
#              one transaction, stop at the first error, nothing half-applied.
#   --yes      skip the "type the host" confirmation (CI only).
#
# Needs: psql (client 17), age (for .age files), gzip.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
die() { echo "restore-db: $*" >&2; exit 1; }

[ "$#" -ge 2 ] || die "usage: restore-db.sh <backup> <target-db-url> [--verify] [--lenient] [--yes]"
backup="$1"; target="$2"; shift 2
verify=0; lenient=0; assume_yes=0
for flag in "$@"; do
  case "$flag" in
    --verify) verify=1 ;; --lenient) lenient=1 ;; --yes) assume_yes=1 ;;
    *) die "unknown option $flag" ;;
  esac
done
[ -f "$backup" ] || die "no such file: $backup"
command -v psql >/dev/null || die "psql is not installed"

host="$(printf '%s' "$target" | sed -E 's#^[a-z]+://([^@/]*@)?([^:/?]+).*#\2#')"
echo "restore-db: target host is $host"
if [ "$assume_yes" -ne 1 ]; then
  read -r -p "Type that host name to confirm this database may be overwritten: " typed
  [ "$typed" = "$host" ] || die "not confirmed"
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
case "$backup" in
  *.age)
    command -v age >/dev/null || die "age is not installed"
    [ -n "${AGE_IDENTITY_FILE:-}" ] && [ -f "$AGE_IDENTITY_FILE" ] || die "set AGE_IDENTITY_FILE to the private key file"
    age -d -i "$AGE_IDENTITY_FILE" "$backup" | gzip -dc >"$work/dump.sql" || die "could not decrypt/decompress (wrong key?)"
    ;;
  *.gz) gzip -dc "$backup" >"$work/dump.sql" ;;
  *) cp "$backup" "$work/dump.sql" ;;
esac
echo "restore-db: dump is $(wc -c <"$work/dump.sql" | tr -d ' ') bytes of SQL"

if [ "$lenient" -eq 1 ]; then
  psql "$target" -v ON_ERROR_STOP=0 -q -f "$work/dump.sql" >/dev/null 2>"$work/errors.log" || true
  errors="$(grep -c 'ERROR:' "$work/errors.log" || true)"
  echo "restore-db: lenient restore finished with $errors statement errors (first 15 below)"
  grep 'ERROR:' "$work/errors.log" | head -15 || true
else
  psql "$target" --single-transaction -v ON_ERROR_STOP=1 -q -f "$work/dump.sql" >/dev/null
  echo "restore-db: restore committed"
fi

# Rows the dump holds for a table: the lines between its COPY header and the terminating \. (-1 = table not in dump).
dump_rows() {
  awk -v h="COPY \"$1\".\"$2\" " 'index($0,h)==1{inb=1;next} inb&&$0==(sprintf("%c",92) "."){print n+0;found=1;exit} inb{n++} END{if(!found)print -1}' "$work/dump.sql"
}

if [ "$verify" -eq 1 ]; then
  bad=0
  while read -r table; do
    case "$table" in ''|'#'*) continue ;; esac
    schema="${table%%.*}"; name="${table#*.}"
    want="$(dump_rows "$schema" "$name")"
    got="$(psql "$target" -Atc "select count(*) from \"$schema\".\"$name\"" 2>/dev/null || echo missing)"
    if [ "$want" = "$got" ]; then echo "  ok   $table: $got rows"; else echo "  FAIL $table: dump has $want, database has $got"; bad=1; fi
  done <"$root/infra/backup/core-tables.txt"
  want="$(dump_rows auth users)"; got="$(psql "$target" -Atc 'select count(*) from auth.users' 2>/dev/null || echo missing)"
  if [ "$want" = "$got" ]; then echo "  ok   auth.users: $got rows"; else echo "  WARN auth.users: dump has $want, database has $got"; [ "$lenient" -eq 1 ] || bad=1; fi
  [ "$bad" -eq 0 ] || die "verification failed"
  echo "restore-db: verified"
fi
