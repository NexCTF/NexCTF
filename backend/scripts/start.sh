#! /usr/bin/env bash

set -e
[ -n "${DEBUG:-}" ] && set -x

export APP_DIR="${APP_DIR:-$(pwd)}"

log() { echo "[start] $*"; }

# --- Prepare (dev + prod): install plugins, migrate, load fixtures ---
if [ -n "${NEXCTF_PLUGINS:-}" ]; then
    log "installing plugins: $NEXCTF_PLUGINS"
    # shellcheck disable=SC2046 # word splitting is how the list becomes arguments
    uv pip install $(echo "$NEXCTF_PLUGINS" | tr ',' ' ')
fi

log "running core migrations"
alembic upgrade head

log "running plugin migrations"
nexctf-plugins upgrade

log "loading fixtures (environment=${ENVIRONMENT:-production})"
manager fixtures load "${ENVIRONMENT:-production}" --strategy skip_existing

log "creating default admin account (if missing)"
manager create-admin

# Dev runs its own server (fastapi dev) after this; skip prod orchestration.
[ "${ENVIRONMENT:-}" = "development" ] && exit 0

# --- Production: generate Caddy config and run the process supervisor ---
DOMAIN="${DOMAIN:-localhost}"
mkdir -p /etc/caddy

if [ -f /certs/cert.pem ] && [ -f /certs/key.pem ]; then
    TLS_DIRECTIVE="tls /certs/cert.pem /certs/key.pem"
    log "TLS: using custom certificates"
else
    TLS_DIRECTIVE="tls internal"
    log "TLS: using internal self-signed certificates"
fi

log "writing Caddyfile for domain: $DOMAIN"
cat > /etc/caddy/Caddyfile << EOF
{
    storage file_system {
        root /data
    }
}

${DOMAIN} {
    ${TLS_DIRECTIVE}

    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle {
        root * /app/frontend/dist
        try_files {path} /index.html
        file_server
    }
}

s3.${DOMAIN} {
    ${TLS_DIRECTIVE}
    reverse_proxy s3:9000
}
EOF

log "starting supervisord"
exec supervisord -n -c /app/supervisord.conf
