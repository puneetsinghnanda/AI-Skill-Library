# Local fixture image for Order Tracker. Never pushed anywhere.
FROM node:22.11-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY db/package.json db/package.json
COPY api/package.json api/package.json
COPY web/package.json web/package.json
RUN npm ci --ignore-scripts

FROM deps AS api
COPY tsconfig.base.json ./
COPY db db
COPY api api
RUN npm run build -w api
USER node
EXPOSE 3000
CMD ["node", "api/dist/server.js"]

FROM deps AS web
COPY tsconfig.base.json ./
COPY web web
USER node
EXPOSE 5174
CMD ["npm", "run", "dev", "-w", "web"]
