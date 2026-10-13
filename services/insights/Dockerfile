# Insights service image (OPS-01 §5.2). One image, entrypoint modes api | worker | migrate | admin | probe.
# Build context is the repository root, because the service validates events against ../../schemas:
#   docker build -f services/insights/Dockerfile -t truminds/insights:X.Y.Z .
# Base images are pinned by digest in the release pipeline (OPS-03 §3); the tags below are the floor.
ARG PYTHON_IMAGE=python:3.12-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.4.30

FROM ${UV_IMAGE} AS uv

# ---- build stage ----
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

# ---- run stage ----
FROM ${PYTHON_IMAGE}
ARG VERSION=0.0.0
ARG REVISION=unknown
LABEL org.opencontainers.image.title="truminds/insights" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin insights
WORKDIR /srv
COPY --from=build /srv /srv
# No secrets, .env files, tests or seed data in the image. Secrets arrive as files under /run/secrets.
ENV PATH="/srv/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SCHEMAS_DIR=/srv/schemas PORTAL_DIST_DIR=/app/portal
USER 10001
EXPOSE 8000 9100 9101
HEALTHCHECK --interval=15s --timeout=3s --retries=4 CMD ["python", "-m", "app.entry", "probe", "live"]
ENTRYPOINT ["python", "-m", "app.entry"]
CMD ["api"]
