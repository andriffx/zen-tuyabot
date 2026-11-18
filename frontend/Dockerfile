# Frontend: SvelteKit static build served by nginx, which also proxies /api and /sse
# to the backend container. Build context is the repository root (see compose).

FROM node:24-bookworm-slim AS build

WORKDIR /app

# Reproducible install first, so the layer survives source edits.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# svelte-kit sync is wired into prebuild; adapter-static writes ./build.
RUN npm run build


FROM nginx:1.27-alpine AS runtime

# SPA + hashed assets, straight from the build stage.
COPY --from=build /app/build /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# The container's own edge settings: no server tokens, sane upload size for a
# restore file (the app caps at 200 MB; nginx must not refuse it first).
RUN printf 'server_tokens off;\nclient_max_body_size 210m;\n' > /etc/nginx/conf.d/00-hardening.conf

EXPOSE 80

# nginx:alpine logs to stdout/stderr through symlinks; keep that (no log files,
# so the container stays compatible with a read-only filesystem).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/healthz || exit 1
