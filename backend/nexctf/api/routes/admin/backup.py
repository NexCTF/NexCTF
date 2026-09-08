import asyncio
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from botocore.exceptions import ClientError
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from fastapi_toolsets.schemas import Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.api.dep import RedisDep, SessionDep
from nexctf.core import s3
from nexctf.exceptions import BackupFailedError
from nexctf.module import backup
from nexctf.module.audit import audit_actor
from nexctf.module.events import emit
from nexctf.schema.backup import AdminBackupList, AdminBackupRead

backup_router = APIRouter(prefix="/backup", tags=["Backup"])

_RESTORE_SCRIPT = Path(__file__).resolve().parents[4] / "scripts/restore.sh"
_RESTORE_LOG = "/tmp/nexctf-restore.log"
_RESTORE_STATUS = Path("/tmp/nexctf-restore.status")


def _key_or_400(key: str) -> str:
    """Validate a caller-supplied backup key, answering 400 when it is not one."""
    try:
        return backup.validate_key(key)
    except backup.BackupError as exc:
        raise BackupFailedError(detail=str(exc))


def _last_restore_status() -> str | None:
    """Outcome of the most recent restore, the only trace a detached run leaves."""
    try:
        return _RESTORE_STATUS.read_text().strip() or None
    except OSError:
        return None


async def _audit(
    session: AsyncSession, redis: Redis, event_type: str, key: str
) -> None:
    """Record a backup action in the audit log."""
    actor_id, ip = audit_actor()
    await emit(
        session,
        redis,
        event_type=event_type,
        actor_id=actor_id,
        ip=ip,
        target_type="backup",
        target_label=key,
    )


def _spawn_restore(key: str) -> None:
    """Start the restore in its own session so it outlives the API it stops."""
    with open(_RESTORE_LOG, "ab") as log:
        subprocess.Popen(
            ["bash", str(_RESTORE_SCRIPT), key],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )


@backup_router.get("")
async def list_backups() -> Response[AdminBackupList]:
    """Every database dump in S3, newest first, plus the last restore's outcome."""
    return Response(
        data=AdminBackupList(
            backups=[AdminBackupRead(**b) for b in await backup.listing()],
            last_restore=_last_restore_status(),
        )
    )


@backup_router.post("", status_code=201)
async def create_backup(
    session: SessionDep, redis: RedisDep
) -> Response[AdminBackupRead]:
    """Dump the database to S3 now."""
    try:
        key, size = await backup.create()
    except backup.BackupError as exc:
        raise BackupFailedError(detail=str(exc))

    await _audit(session, redis, "backup.created", key)
    return Response(
        data=AdminBackupRead(
            key=key,
            size=size,
            created_at=datetime.now(UTC),
            revision=backup.revision_of(key),
        )
    )


@backup_router.get("/download")
async def download_backup(key: str) -> StreamingResponse:
    """Stream a dump through the authenticated API."""
    _key_or_400(key)

    async def body():
        async with s3.stream(key) as chunks:
            async for chunk in chunks:
                yield chunk

    filename = key.removeprefix(backup.PREFIX)
    return StreamingResponse(
        body(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@backup_router.post("/restore")
async def restore_backup(
    session: SessionDep, redis: RedisDep, key: str
) -> Response[None]:
    """Stop the app, restore the dump, migrate and start again, in the background.

    Only the bundled image can orchestrate this; elsewhere the operator runs
    ``manager restore <key>`` with the app stopped.
    """
    _key_or_400(key)
    if shutil.which("supervisorctl") is None or not _RESTORE_SCRIPT.exists():
        raise BackupFailedError(
            detail=(
                "Automatic restore needs the bundled NexCTF image. Stop the app "
                f"and run: manager restore {key}"
            )
        )
    try:
        await s3.head(key)
    except ClientError:
        raise BackupFailedError(detail=f"No backup at {key!r}")

    await _audit(session, redis, "backup.restored", key)
    await session.commit()

    await asyncio.to_thread(_spawn_restore, key)
    return Response(message="Restore started; the platform is restarting.")


@backup_router.delete("")
async def delete_backup(
    session: SessionDep, redis: RedisDep, key: str
) -> Response[None]:
    """Delete a dump from S3."""
    _key_or_400(key)
    await s3.delete(key)

    await _audit(session, redis, "backup.deleted", key)
    return Response()
