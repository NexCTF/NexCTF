FROM node:22-slim AS node
FROM oven/bun:alpine AS frontend-builder

WORKDIR /app

COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

COPY frontend/ ./
RUN bun run build


FROM caddy:2-alpine AS caddy-bin

FROM python:3.13-slim

ARG VERSION=dev
LABEL org.opencontainers.image.title="NexCTF" \
      org.opencontainers.image.description="NexCTF CTF Platform" \
      org.opencontainers.image.version=${VERSION}

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends --no-install-suggests \
        git curl supervisor libcap2-bin \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --gid 1000 nexctf \
    && adduser --uid 1000 --gid 1000 --disabled-password --gecos "" nexctf \
    && mkdir -p /app /data /etc/caddy \
    && chown nexctf:nexctf /app /data /etc/caddy

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules/
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

COPY --from=caddy-bin /usr/bin/caddy /usr/bin/caddy
# Allow caddy to bind to ports < 1024 without root
RUN setcap cap_net_bind_service=+ep /usr/bin/caddy

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /uvx /bin/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV PATH="/app/.venv/bin:$PATH"

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/
USER nexctf

# Install dependencies (no dev tools in production image)
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,uid=1000,gid=1000,target=/home/nexctf/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

ENV PYTHONPATH=/app
ENV WORKERS=4

COPY --chown=nexctf:nexctf backend/scripts/start.sh backend/scripts/run_plugin_migration.py /app/scripts/
COPY --chown=nexctf:nexctf backend/scripts/plugin_alembic /app/scripts/plugin_alembic
COPY --chown=nexctf:nexctf docker/with-prefix.sh /app/scripts/with-prefix.sh
RUN chmod +x /app/scripts/start.sh /app/scripts/with-prefix.sh
COPY --chown=nexctf:nexctf backend/pyproject.toml backend/uv.lock backend/alembic.ini /app/
COPY --chown=nexctf:nexctf backend/nexctf /app/nexctf
COPY --chown=nexctf:nexctf backend/plugins_store /app/plugins_store

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,uid=1000,gid=1000,target=/home/nexctf/.cache/uv \
    uv sync --frozen --no-dev

COPY --chown=nexctf:nexctf docker/supervisord.conf /app/supervisord.conf
COPY --chown=nexctf:nexctf --from=frontend-builder /app/dist /app/frontend/dist

CMD ["bash", "/app/scripts/start.sh"]
