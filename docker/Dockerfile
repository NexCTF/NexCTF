FROM oven/bun:alpine AS frontend-builder

WORKDIR /app

COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

COPY frontend/ ./
RUN bun run build


FROM caddy:2-alpine AS caddy-bin

FROM debian:trixie-slim

LABEL org.opencontainers.image.title="NexCTF" \
      org.opencontainers.image.description="Next generation of capture the flag platform" \
      org.opencontainers.image.source="https://github.com/NexCTF/NexCTF" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends --no-install-suggests \
        git curl supervisor libcap2-bin ca-certificates \
    && install -d /etc/apt/keyrings \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /etc/apt/keyrings/pgdg.asc \
    && echo "deb [signed-by=/etc/apt/keyrings/pgdg.asc] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends --no-install-suggests \
        postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 nexctf \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash nexctf \
    && mkdir -p /app /data /etc/caddy /var/log/nexctf /home/nexctf/.cache/uv \
    && chown nexctf:nexctf /app /data /etc/caddy /var/log/nexctf \
    && chown -R nexctf:nexctf /home/nexctf/.cache

COPY --from=caddy-bin /usr/bin/caddy /usr/bin/caddy
# Allow caddy to bind to ports < 1024 without root
RUN setcap cap_net_bind_service=+ep /usr/bin/caddy

# Install uv
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /bin/

# Place executables in the environment at the front of the path
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Compile bytecode
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
ENV UV_COMPILE_BYTECODE=1

# uv Cache
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

WORKDIR /app/

# uv-managed CPython, built with BOLT, mimalloc and the tail-call interpreter
ENV UV_PYTHON_INSTALL_DIR=/python \
    UV_PYTHON_PREFERENCE=only-managed
COPY --chown=nexctf:nexctf backend/.python-version ./
RUN uv python install

USER nexctf

# Install dependencies (no dev tools in production image)
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,uid=1000,gid=1000,target=/home/nexctf/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

ENV PYTHONPATH=/app
ENV WORKERS=4

COPY --chown=nexctf:nexctf backend/scripts/start.sh backend/scripts/restore.sh /app/scripts/
COPY --chown=nexctf:nexctf docker/with-prefix.sh /app/scripts/with-prefix.sh
RUN chmod +x /app/scripts/start.sh /app/scripts/restore.sh /app/scripts/with-prefix.sh
COPY --chown=nexctf:nexctf backend/pyproject.toml backend/uv.lock backend/alembic.ini /app/
COPY --chown=nexctf:nexctf backend/nexctf /app/nexctf

# Sync the project
# Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
RUN --mount=type=cache,uid=1000,gid=1000,target=/home/nexctf/.cache/uv \
    uv sync --frozen --no-dev

# Pin core dependencies for plugin installs, so a plugin cannot move them
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o /app/constraints.txt
ENV UV_CONSTRAINT=/app/constraints.txt

COPY --chown=nexctf:nexctf docker/supervisord.conf /app/supervisord.conf
COPY --chown=nexctf:nexctf --from=frontend-builder /app/dist /app/frontend/dist

CMD ["bash", "/app/scripts/start.sh"]
