# One-machine TEST environment image (ADR 0006, deploy/README.md "Run the test environment on one
# machine for 6 testers"). The insights service with the portal built in GitHub mode and served by
# the api itself (SERVE_PORTAL=true): one origin, one published port, no edge.
# Not for production: production uses services/insights/Dockerfile + portal/Dockerfile behind the edge.
#
# Build context is the repository root (compose.test.yml does this):
#   docker build -f deploy/images/test-env/Dockerfile -t truminds/insights-test .
ARG NODE_IMAGE=node:20-alpine
ARG PYTHON_IMAGE=python:3.12-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.4.30

FROM ${UV_IMAGE} AS uv

# ---- portal, GitHub sign-in mode, TEST ENVIRONMENT banner ----
FROM ${NODE_IMAGE} AS portal
WORKDIR /app
ENV CI=1 PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm_config_audit=false npm_config_fund=false
COPY portal/package.json portal/package-lock.json ./
RUN npm ci
COPY portal/ ./
ARG VITE_MARKETPLACE_REPO_URL=
ENV VITE_IDENTITY_PROVIDER=github \
    VITE_ENVIRONMENT=test \
    VITE_ENV_NAME=test \
    VITE_MARKETPLACE_REPO_URL=${VITE_MARKETPLACE_REPO_URL}
RUN npm run build

# ---- insights service (same steps as services/insights/Dockerfile) ----
FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/srv/.venv
WORKDIR /srv
COPY services/insights/pyproject.toml services/insights/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY services/insights/app ./app
COPY services/insights/alembic ./alembic
COPY services/insights/alembic.ini ./
COPY schemas /srv/schemas

FROM ${PYTHON_IMAGE}
LABEL org.opencontainers.image.title="truminds/insights-test"
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin insights
WORKDIR /srv
COPY --from=build /srv /srv
COPY --from=portal /app/dist /app/portal
ENV PATH="/srv/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SCHEMAS_DIR=/srv/schemas PORTAL_DIST_DIR=/app/portal SERVE_PORTAL=true
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=4 CMD ["python", "-m", "app.entry", "probe", "live"]
ENTRYPOINT ["python", "-m", "app.entry"]
CMD ["api"]
