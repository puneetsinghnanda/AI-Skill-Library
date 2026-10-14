# syntax=docker/dockerfile:1
# Verifier image node-20@1 (SDD-03 §5.5; SEC-01 §5.5, §7.1, §8.4). Node.js 20 projects.
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

# --- verifier: Node.js 20 plus ESLint SARIF formatter, Semgrep and gitleaks
FROM node:20.18.1-bookworm-slim
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*
RUN npm install -g --no-fund --no-audit @microsoft/eslint-formatter-sarif@3.1.0 \
 && npm cache clean --force
COPY --from=gitleaks /usr/local/bin/gitleaks /usr/local/bin/gitleaks
# Semgrep (SAST) in its own virtualenv. The ruleset is snapshotted into the image at build time,
# because every step but prepare runs with --network none; the image digest fixes the snapshot.
ARG SEMGREP_VERSION=1.95.0
RUN python3 -m venv /opt/semgrep \
 && /opt/semgrep/bin/pip install --no-cache-dir "semgrep==${SEMGREP_VERSION}" \
 && ln -s /opt/semgrep/bin/semgrep /usr/local/bin/semgrep \
 && mkdir -p /opt/verifier/semgrep \
 && /opt/semgrep/bin/python -c "import urllib.request as u; u.urlretrieve('https://semgrep.dev/c/p/default', '/opt/verifier/semgrep/default.yml')"
# Non-root user 1000 (tsl runs every step with --user 1000:1000), writable cache and report mounts.
RUN (getent passwd 1000 >/dev/null || useradd --uid 1000 --user-group --no-create-home --shell /usr/sbin/nologin verifier) \
 && mkdir -p /src /cache /out \
 && chown 1000:1000 /cache /out
ENV HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    SEMGREP_ENABLE_VERSION_CHECK=0 \
    SEMGREP_SEND_METRICS=off \
    npm_config_cache=/cache/npm \
    npm_config_update_notifier=false \
    npm_config_fund=false
USER 1000:1000
WORKDIR /src
ENTRYPOINT []
CMD ["sh"]
