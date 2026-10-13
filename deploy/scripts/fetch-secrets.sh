#!/usr/bin/env bash
# fetch-secrets.sh (OPS-01 §7.2): copy every secret the stack needs from the host's secret store into
# /run/truminds-secrets (tmpfs, root-owned, files 0400) before `docker compose up`.
#
# Run by truminds-secrets.service (deploy/systemd). It authenticates with the VM's machine identity;
# no credential is stored in this script or in git. The secret store is TBD (OQ-02), so the backend is
# a small adapter chosen with SECRET_BACKEND:
#
#   vault   HashiCorp-compatible KV v2 via the `vault` CLI, machine login done by the host agent
#           (VAULT_ADDR from the environment, token from the agent sink). SECRET_PATH = kv mount path.
#   file    a root-only directory already provisioned by config management (SECRET_SOURCE_DIR).
#           For staging hosts without a vault; the directory must be on an encrypted disk.
#
# Usage: fetch-secrets.sh [--check]     --check lists missing names and exits 1 if any are missing.
set -euo pipefail
umask 077

DEST="${SECRET_DEST:-/run/truminds-secrets}"
BACKEND="${SECRET_BACKEND:-vault}"
SECRET_PATH="${SECRET_PATH:-truminds/insights}"
SOURCE_DIR="${SECRET_SOURCE_DIR:-/etc/truminds/secrets.d}"
SECRETS_GID="${SECRETS_GID:-990}"   # must match group_add in compose.prod.yml

# Names only (OPS-01 §7.3). db_reveal_password is the insights_reveal role (SDD-09 §5.3).
SECRETS=(
  db_superuser_password db_owner_password db_app_password db_read_password db_reveal_password
  pepper data_key catalogue_token backup_cipher_key backup_store_credentials
)
# TLS material lands in sub-directories mounted by edge and postgres.
TLS_FILES=(
  "tls/intranet.crt" "tls/intranet.key" "tls/public.crt" "tls/public.key"
  "db-tls/server.crt" "db-tls/server.key" "db-tls/ca.crt"
)

fetch_one() {   # $1 = name (may contain a slash for TLS files); writes to stdout
  local name="$1"
  case "$BACKEND" in
    vault) vault kv get -field=value "${SECRET_PATH}/${name//\//_}" ;;
    file)  cat "${SOURCE_DIR}/${name}" ;;
    *) echo "unknown SECRET_BACKEND=${BACKEND}" >&2; return 2 ;;
  esac
}

check_only=0
[[ "${1:-}" == "--check" ]] && check_only=1

if [[ $check_only -eq 0 ]]; then
  if ! mountpoint -q "$DEST"; then
    mkdir -p "$DEST"
    mount -t tmpfs -o size=4m,mode=0700,uid=0,gid=0,noexec,nosuid,nodev tmpfs "$DEST"
  fi
  mkdir -p "$DEST/tls" "$DEST/db-tls"
fi

missing=0
for name in "${SECRETS[@]}" "${TLS_FILES[@]}"; do
  if [[ $check_only -eq 1 ]]; then
    fetch_one "$name" >/dev/null 2>&1 || { echo "missing: $name"; missing=1; }
    continue
  fi
  tmp="$(mktemp -p "$DEST" .fetch.XXXXXX)"
  if fetch_one "$name" > "$tmp" && [[ -s "$tmp" ]]; then
    chmod 0400 "$tmp"
    mv -f "$tmp" "$DEST/$name"
  else
    rm -f "$tmp"
    echo "missing: $name" >&2
    missing=1
  fi
done

if [[ $check_only -eq 0 && $missing -eq 0 ]]; then
  # Docker file secrets keep the host file's owner and mode. Every container that reads secrets runs
  # with the supplementary group SECRETS_GID (compose `group_add`), so files are root:SECRETS_GID 0440.
  chown -R "0:${SECRETS_GID}" "$DEST"
  find "$DEST" -type f -exec chmod 0440 {} +
  chmod 0750 "$DEST" "$DEST/tls" "$DEST/db-tls"
  # PostgreSQL refuses a server key readable by others than its owner: give it to the postgres uid.
  chown 999:999 "$DEST/db-tls/server.key" && chmod 0400 "$DEST/db-tls/server.key"
  echo "fetched ${#SECRETS[@]} secrets and ${#TLS_FILES[@]} TLS files into $DEST"
fi
exit $missing
