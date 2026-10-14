# Hosted TEST environment image for Render (deploy/render/README.md, ADR 0006 addendum).
# One container: the portal built in GitHub sign-in mode, served by the insights service itself
# (same origin, no edge), the API, GitHub sign-in and the worker jobs (`python -m app.entry allinone`).
# Not for production: production uses services/insights/Dockerfile + portal/Dockerfile behind the edge.
#
# Build context is the repository root (render.yaml sets this):
#   docker build -f deploy/render/Dockerfile -t truminds/skills-test .
# Base images are named directly (not through ARG) so hadolint can check the tags.
FROM ghcr.io/astral-sh/uv:0.4.30 AS uv

# ---- portal: GitHub sign-in, TEST ENVIRONMENT banner, API on the same origin ----
FROM node:22-alpine AS portal
WORKDIR /app
ENV CI=1 PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm_config_audit=false npm_config_fund=false
COPY portal/package.json portal/package-lock.json ./
RUN npm ci
COPY portal/ ./
# Render passes service environment variables to the build as build arguments.
ARG VITE_MARKETPLACE_REPO_URL=
ENV VITE_IDENTITY_PROVIDER=github \
    VITE_ENVIRONMENT=test \
    VITE_ENV_NAME=test \
    VITE_API_BASE_URL= \
    VITE_MARKETPLACE_REPO_URL=${VITE_MARKETPLACE_REPO_URL}
RUN npm run build

# ---- insights service and the catalogue source (same steps as services/insights/Dockerfile) ----
FROM python:3.12-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/srv/.venv
WORKDIR /srv
COPY services/insights/pyproject.toml services/insights/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY services/insights/app ./app
COPY services/insights/alembic ./alembic
COPY services/insights/alembic.ini ./
COPY schemas /srv/schemas
# What the start-up catalogue sync reads (app/catalogue/sync.py): skills, workflows, pods, versions.
COPY plugins/truminds /srv/catalogue/plugins/truminds
COPY pods /srv/catalogue/pods
COPY tsl/src/tsl/__init__.py /srv/catalogue/tsl/src/tsl/__init__.py
ARG RENDER_GIT_COMMIT=unknown
RUN python -c "import json, sys; v = json.load(open('/srv/catalogue/plugins/truminds/.claude-plugin/plugin.json'))['version']; sys.stdout.write(f'v{v} ${RENDER_GIT_COMMIT}\n')" \
      > /srv/catalogue/.release-tag

# ---- run stage ----
FROM python:3.12-slim
LABEL org.opencontainers.image.title="truminds/skills-test"
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin insights
WORKDIR /srv
COPY --from=build /srv /srv
COPY --from=portal /app/dist /app/portal
# No secrets here: Render injects them as environment variables at run time (render.yaml).
ENV PATH="/srv/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SCHEMAS_DIR=/srv/schemas SERVE_PORTAL_DIR=/app/portal CATALOGUE_SOURCE_DIR=/srv/catalogue \
    PORT=10000 DATABASE_POOL_SIZE=2
USER 10001
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=3s --retries=4 CMD ["python", "-m", "app.entry", "probe", "live"]
ENTRYPOINT ["python", "-m", "app.entry"]
CMD ["allinone"]
