#! /usr/bin/env bash

set -e
[ -n "${DEBUG:-}" ] && set -x

export APP_DIR="${APP_DIR:-$(pwd)}"

log() { echo "[start] $*"; }

# --- Prepare (dev + prod): install store plugins, migrate, load fixtures ---
for plugin in "$APP_DIR"/plugins_store/*/; do
    if [ -f "$plugin/pyproject.toml" ]; then
        plugin_name="$(basename "$plugin")"
        log "installing plugin: $plugin_name"
        uv pip install -e "$plugin"
    fi
done

log "running core migrations"
alembic upgrade head

for plugin in "$APP_DIR"/plugins_store/*/; do
    if [ -d "$plugin/alembic/versions" ]; then
        plugin_name="$(basename "$plugin")"
        log "running migrations for plugin: $plugin_name"
        python "$APP_DIR/scripts/run_plugin_migration.py" "$plugin" upgrade head
    fi
done

log "loading fixtures (environment=${ENVIRONMENT:-production})"
manager fixtures load "${ENVIRONMENT:-production}" --strategy skip_existing

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
