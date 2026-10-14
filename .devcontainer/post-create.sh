#!/usr/bin/env bash
# One-time setup inside the dev container (DEV-01 §3). Installs uv, Node 20 next to Node 22,
# PostgreSQL 16 binaries for the throwaway test clusters, and the pre-commit hooks.
set -euo pipefail

pipx install uv
pipx install pre-commit

# Node 20 for the portal (portal/.nvmrc); Node 22 stays the default (examples/sample-system/.nvmrc)
# shellcheck disable=SC1091
. "${NVM_DIR:-/usr/local/share/nvm}/nvm.sh"
nvm install 20
nvm alias default 22

# PostgreSQL 16 from the PostgreSQL Global Development Group apt repository
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc
echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
  | sudo tee /etc/apt/sources.list.d/pgdg.list >/dev/null
sudo rm -f /etc/apt/sources.list.d/yarn*.list
sudo apt-get update
sudo apt-get install -y --no-install-recommends postgresql-16

# The workspace is bind-mounted from the host with a different owner; without this, git (and pre-commit) refuse
# it as "dubious ownership".
git config --global --add safe.directory "$PWD"
pre-commit install
echo "Dev container ready. Next: make test-all"
