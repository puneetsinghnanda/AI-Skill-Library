# syntax=docker/dockerfile:1
# Verifier image node-22@1 (SDD-03 §5.5; SEC-01 §5.5, §7.1, §8.4). Node.js 22 projects.
# Carries the PostgreSQL 16 binaries so database tests run offline on loopback (the sample system's
# PG_BIN default, examples/sample-system/db/testing/pg-harness.ts).
# Built by .github/workflows/verifier-images.yml; profile.yaml references the built image by digest only.
# Base images and tools are pinned by version. Debian packages follow the base image's release and
# are recorded in the image SBOM that the workflow produces.
# tsl runs each step with --network none (every step but prepare), --read-only, --tmpfs /tmp,
# a read-only source mount, --user 1000:1000, --cap-drop ALL, --security-opt no-new-privileges,
# --cpus 2, --memory 4g and --pids-limit 512 (tsl/src/tsl/harness/verifier.py).

# --- gitleaks, pinned by version and checked against its release SHA-256 (SEC-01 §7.1)
FROM python:3.12.7-slim-bookworm AS gitleaks
ARG GITLEAKS_VERSION=8.21.2
ARG GITLEAKS_SHA256=5bc41815076e6ed6ef8fbecc9d9b75bcae31f39029ceb55da08086315316e3ba
RUN python3 -c "import hashlib, os, tarfile, urllib.request as u; \
v = os.environ['GITLEAKS_VERSION']; f = '/tmp/gitleaks.tgz'; \
u.urlretrieve(f'https://github.com/gitleaks/gitleaks/releases/download/v{v}/gitleaks_{v}_linux_x64.tar.gz', f); \
d = hashlib.sha256(open(f, 'rb').read()).hexdigest(); \
assert d == os.environ['GITLEAKS_SHA256'], f'gitleaks checksum mismatch: {d}'; \
tarfile.open(f).extract('gitleaks', '/usr/local/bin', filter='data')"

# --- Node.js 22, copied from the official image
FROM node:22.11.0-bookworm-slim AS node

# --- verifier: PostgreSQL 16 base plus Node.js, ESLint SARIF formatter, Semgrep and gitleaks
FROM postgres:16.4-bookworm
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && node --version
RUN npm install -g --no-fund --no-audit @microsoft/eslint-formatter-sarif@3.1.0 \
 && npm cache clean --force
COPY --from=gitleaks /usr/local/bin/gitleaks /usr/local/bin/gitleaks
# Semgrep (SAST) in its own virtualenv. The ruleset is snapshotted into the image at build time,
# because every step but prepare runs with --network none; the image digest fixes the snapshot.
ARG SEMGREP_VERSION=1.95.0
# semgrep's OpenTelemetry instrumentation imports pkg_resources, which Python 3.12+ venvs no longer ship.
ARG SETUPTOOLS_VERSION=75.8.0
RUN python3 -m venv /opt/semgrep \
 && /opt/semgrep/bin/pip install --no-cache-dir "semgrep==${SEMGREP_VERSION}" "setuptools==${SETUPTOOLS_VERSION}" \
 && ln -s /opt/semgrep/bin/semgrep /usr/local/bin/semgrep \
 && mkdir -p /opt/verifier/semgrep \
 && /opt/semgrep/bin/python -c "import urllib.request as u; u.urlretrieve('https://semgrep.dev/c/p/default', '/opt/verifier/semgrep/default.yml')"
# Non-root user 1000 (tsl runs every step with --user 1000:1000), writable cache and report mounts.
RUN (getent passwd 1000 >/dev/null || useradd --uid 1000 --user-group --no-create-home --shell /usr/sbin/nologin verifier) \
 && mkdir -p /src /cache /out \
 && chown 1000:1000 /cache /out
# semgrep runs its pysemgrep helper from the same virtualenv, so that folder must be on PATH. It goes
# last, so the venv's python never shadows the image's own.
ENV PATH="$PATH:/opt/semgrep/bin" \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    SEMGREP_ENABLE_VERSION_CHECK=0 \
    SEMGREP_SEND_METRICS=off \
    npm_config_cache=/cache/npm \
    npm_config_update_notifier=false \
    npm_config_fund=false \
    PG_BIN=/usr/lib/postgresql/16/bin
USER 1000:1000
# Smoke check as the verifier user: fail the build if a scanner cannot start.
RUN semgrep --version && gitleaks version
WORKDIR /src
ENTRYPOINT []
CMD ["sh"]
