#! /usr/bin/env bash
# Restore a database backup inside the bundled image: stops the app, replaces
# the database, migrates it and starts the app again. Spawned detached by the
# admin API, which is itself stopped below.

set -e
[ -n "${DEBUG:-}" ] && set -x

cd "$(dirname "$0")/.."

KEY="$1"
[ -z "$KEY" ] && { echo "usage: restore.sh <backups/...>" >&2; exit 2; }

STATUS_FILE=/tmp/nexctf-restore.status

log() { echo "[restore] $*"; }

# Record the outcome for the UI to read and bring the app back, whether or not
# the restore succeeded.
finish() {
    rc=$?
    if [ "$rc" -eq 0 ]; then
        echo "ok $KEY" > "$STATUS_FILE"
    else
        echo "failed $KEY (exit $rc, see /tmp/nexctf-restore.log)" > "$STATUS_FILE"
    fi
    log "starting backend and scheduler"
    supervisorctl start backend scheduler
}

echo "running $KEY" > "$STATUS_FILE"

log "stopping backend and scheduler"
supervisorctl stop backend scheduler
trap finish EXIT

log "restoring $KEY"
manager restore "$KEY" --yes

log "running core migrations"
alembic upgrade head

log "running plugin migrations"
nexctf-plugins upgrade
