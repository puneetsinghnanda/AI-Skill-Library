# Portal image `truminds/portal` (OPS-01 §5.2, SDD-09 §10): static Vite build served by unprivileged
# nginx on :8080. Fits the `portal` service in deploy/compose/compose.prod.yml (uid 101, read-only
# root filesystem, tmpfs /tmp and /var/cache/nginx, cap_drop ALL).
#
#   docker build -t truminds/portal:X.Y.Z \
#     --build-arg VITE_ENTRA_TENANT_ID=... --build-arg VITE_ENTRA_CLIENT_ID=... portal/
#
# Base images are pinned by digest in the release pipeline (OPS-03 §3); the tags below are the floor.
# VITE_* values are build-time and not secret (the SPA holds no secret); see .env.example.
ARG NODE_IMAGE=node:20-alpine
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.27-alpine

# ---- build stage ----
FROM ${NODE_IMAGE} AS build
WORKDIR /app
ENV CI=1 PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm_config_audit=false npm_config_fund=false
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_ENTRA_TENANT_ID
ARG VITE_ENTRA_CLIENT_ID
ARG VITE_ENTRA_REDIRECT_URI=
ARG VITE_API_SCOPE=api://truminds-insights/Portal.Read
ARG VITE_API_BASE_URL=
ARG VITE_MARKETPLACE_REPO_URL
ARG VITE_PILOT_MAILTO=
ARG VITE_HELP_URL=
ARG VITE_ENV_NAME=prod
ARG VITE_BUILD_ID=unknown
ARG VITE_RD1_NAME_REVEAL_ROLES=eng_lead,admin
ARG VITE_RD2_ENGINEER_RUN_SCOPE=system
ARG VITE_RD3_QUESTION_TEXT_IN_CLOUD=false
ENV VITE_ENTRA_TENANT_ID=${VITE_ENTRA_TENANT_ID} \
    VITE_ENTRA_CLIENT_ID=${VITE_ENTRA_CLIENT_ID} \
    VITE_ENTRA_REDIRECT_URI=${VITE_ENTRA_REDIRECT_URI} \
    VITE_API_SCOPE=${VITE_API_SCOPE} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_MARKETPLACE_REPO_URL=${VITE_MARKETPLACE_REPO_URL} \
    VITE_PILOT_MAILTO=${VITE_PILOT_MAILTO} \
    VITE_HELP_URL=${VITE_HELP_URL} \
    VITE_ENV_NAME=${VITE_ENV_NAME} \
    VITE_BUILD_ID=${VITE_BUILD_ID} \
    VITE_RD1_NAME_REVEAL_ROLES=${VITE_RD1_NAME_REVEAL_ROLES} \
    VITE_RD2_ENGINEER_RUN_SCOPE=${VITE_RD2_ENGINEER_RUN_SCOPE} \
    VITE_RD3_QUESTION_TEXT_IN_CLOUD=${VITE_RD3_QUESTION_TEXT_IN_CLOUD}
# Typecheck, production build, then the bundle gate (no mocks, no test-auth fixture: TC-POR-010).
RUN test -n "$VITE_ENTRA_TENANT_ID" && test -n "$VITE_ENTRA_CLIENT_ID" \
    || (echo "VITE_ENTRA_TENANT_ID and VITE_ENTRA_CLIENT_ID build args are required" && exit 1)
RUN npm run build

# ---- run stage ----
FROM ${NGINX_IMAGE}
ARG VERSION=0.0.0
ARG REVISION=unknown
LABEL org.opencontainers.image.title="truminds/portal" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
CMD ["nginx", "-g", "daemon off;"]
