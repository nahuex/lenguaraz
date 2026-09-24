# SPDX-License-Identifier: Apache-2.0
# Lenguaraz — single image: built audience view + API. Non-root, ffmpeg as a separate program.

# --- stage 1: audience view -------------------------------------------------------------
FROM node:24-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- stage 2: runtime ----------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    HOST=0.0.0.0 \
    PORT=8000 \
    WEB_DIST=/app/web/dist

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 lenguaraz \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin lenguaraz

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
RUN uv sync --frozen --no-dev --no-install-project
COPY lenguaraz/ ./lenguaraz/
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist ./web/dist
COPY stages.yaml ./stages.yaml
COPY samples/ ./samples/
COPY examples/ ./examples/
RUN chown -R lenguaraz:lenguaraz /app

USER lenguaraz
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"]

CMD ["/app/.venv/bin/lenguaraz", "serve"]
