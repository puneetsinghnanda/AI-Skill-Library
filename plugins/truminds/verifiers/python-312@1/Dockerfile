# syntax=docker/dockerfile:1
# Verifier image python-312@1 (SDD-03 §5.5; SEC-01 §5.5, §7.1, §8.4). Python 3.12 projects managed with uv (uv.lock).
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

# --- verifier: Python 3.12 plus uv, Ruff, Semgrep and gitleaks
FROM python:3.12.7-slim-bookworm
ARG UV_VERSION=0.5.4
ARG RUFF_VERSION=0.7.4
RUN python3 -m venv /opt/tools \
 && /opt/tools/bin/pip install --no-cache-dir "uv==${UV_VERSION}" "ruff==${RUFF_VERSION}" \
 && ln -s /opt/tools/bin/uv /usr/local/bin/uv \
 && ln -s /opt/tools/bin/ruff /usr/local/bin/ruff
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
    UV_CACHE_DIR=/cache/uv \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/cache/w/.venv \
    RUFF_CACHE_DIR=/tmp/.ruff_cache
USER 1000:1000
WORKDIR /src
ENTRYPOINT []
CMD ["sh"]
