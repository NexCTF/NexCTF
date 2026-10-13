#! /usr/bin/env bash

set -e
[ -n "${DEBUG:-}" ] && set -x

export APP_DIR="${APP_DIR:-$(pwd)}"

log() { echo "[start] $*"; }

# Masks the credentials of every URL in $1 (user:secret@ -> user:****@, token@ -> ****@).
redact_urls() {
    sed -E 's#://([^/@:]+):[^/@]*@#://\1:****@#g; s#://[^/@:]+@#://****@#g' <<< "$1"
}

# --- Prepare (dev + prod): install plugins, migrate, load fixtures ---
if [ -n "${NEXCTF_PLUGINS:-}" ]; then
    log "installing plugins: $(redact_urls "$NEXCTF_PLUGINS")"
    # shellcheck disable=SC2086 # word splitting is how the list becomes arguments
    uv pip install ${NEXCTF_PLUGINS//,/ }
fi

log "running core migrations"
alembic upgrade head

log "running plugin migrations"
nexctf-plugins upgrade

FIXTURE_CONTEXTS="${ENVIRONMENT:-production}"
[ "${DEMO_DATA:-}" = "true" ] && FIXTURE_CONTEXTS="$FIXTURE_CONTEXTS demo"

log "loading fixtures (contexts: $FIXTURE_CONTEXTS)"
# shellcheck disable=SC2086 # word splitting is how the list becomes arguments
manager fixtures load $FIXTURE_CONTEXTS --strategy skip_existing

log "creating default admin account (if missing)"
manager create-admin

# Dev runs its own server (fastapi dev) after this; skip prod orchestration.
[ "${ENVIRONMENT:-}" = "development" ] && exit 0

# --- Production: generate Caddy config and run the process supervisor ---
DOMAIN="${DOMAIN:-localhost}"
mkdir -p /etc/caddy

SCHEME=""
SERVERS_DIRECTIVE=""
if [ "${TLS_TERMINATED_UPSTREAM:-}" = "true" ]; then
    SCHEME="http://"
    TLS_DIRECTIVE=""
    # Keep the X-Forwarded-For of the proxy in front instead of replacing it.
    SERVERS_DIRECTIVE="servers {
        trusted_proxies static private_ranges
    }"
    log "TLS: terminated upstream, serving plain HTTP"
elif [ -f /certs/cert.pem ] && [ -f /certs/key.pem ]; then
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
    ${SERVERS_DIRECTIVE}
}

${SCHEME}${DOMAIN} {
    ${TLS_DIRECTIVE}

    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle /metrics {
        reverse_proxy 127.0.0.1:8000
    }

    handle {
        import /app/security-headers.caddy
        root * /app/frontend/dist
        try_files {path} /index.html
        file_server
    }
}

${SCHEME}s3.${DOMAIN} {
    ${TLS_DIRECTIVE}
    reverse_proxy ${S3_HOST:-s3}:${S3_PORT:-9000}
}
EOF

log "starting supervisord"
exec supervisord -n -c /app/supervisord.conf
