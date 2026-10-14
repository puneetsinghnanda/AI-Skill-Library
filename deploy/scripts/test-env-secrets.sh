#!/usr/bin/env bash
# Generate the database passwords, pseudonym pepper and data key for the one-machine TEST
# environment (deploy/README.md, ADR 0006) into deploy/compose/test-secrets/ (git-ignored).
# Existing files are kept, so re-running never rotates a key under existing data.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dir="${1:-$here/../compose/test-secrets}"
mkdir -p "$dir"
chmod 700 "$dir"
gen() {
  local name="$1" cmd="$2"
  if [[ ! -s "$dir/$name" ]]; then
    (umask 077 && eval "$cmd" > "$dir/$name")
    echo "created $name"
  fi
}
gen db_superuser_password "openssl rand -hex 24"
gen db_owner_password     "openssl rand -hex 24"
gen db_app_password       "openssl rand -hex 24"
gen db_read_password      "openssl rand -hex 24"
gen db_reveal_password    "openssl rand -hex 24"
gen pepper                "openssl rand -base64 48 | tr -d '\n'"
gen data_key              "openssl rand -base64 32 | tr -d '\n'"
# The containers run as uid 10001 (insights) and 999 (postgres); let both read the files.
chmod 644 "$dir"/*
chmod 755 "$dir"
echo "test secrets in $dir"
