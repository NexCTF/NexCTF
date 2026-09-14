"""Database dump and restore against the S3 ``backups/`` prefix."""

import asyncio
import logging
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import text

from nexctf.core import s3
from nexctf.core.config import settings
from nexctf.core.db import get_db_context
from nexctf.schema.backup import BackupSource

logger = logging.getLogger(__name__)

PREFIX = "backups/"
_SOURCES = "|".join(BackupSource)
_KEY_RE = re.compile(
    rf"^nexctf-(?P<stamp>\d{{8}}T\d{{6}}Z)"
    rf"(?:-(?P<source>{_SOURCES}))?"
    rf"(?:-(?P<revision>[0-9A-Za-z_]+))?\.dump$"
)
_REVISION_RE = re.compile(r"[0-9A-Za-z_]+")
_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


class BackupError(Exception):
    """A dump or restore could not be carried out."""


def _pg_env() -> dict[str, str]:
    """Environment for pg_dump / pg_restore, carrying the password out of argv."""
    return {**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD}


def _pg_args() -> list[str]:
    """Connection flags every Postgres client binary is called with."""
    return [
        "-h",
        settings.POSTGRES_SERVER,
        "-p",
        str(settings.POSTGRES_PORT),
        "-U",
        settings.POSTGRES_USER,
        "-d",
        settings.POSTGRES_DB,
    ]


async def _run(program: str, *args: str) -> None:
    """Run a Postgres client binary, raising BackupError on a non-zero exit."""
    if shutil.which(program) is None:
        raise BackupError(
            f"{program} is not installed: the database backup feature needs "
            "postgresql-client on the host running NexCTF."
        )
    proc = await asyncio.create_subprocess_exec(
        program,
        *_pg_args(),
        *args,
        env=_pg_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise BackupError(f"{program} failed: {stderr.decode(errors='replace')[-500:]}")


async def current_revision() -> str | None:
    """Read the Alembic revision the live database is stamped with."""
    async with get_db_context() as session:
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        return result.scalar_one_or_none()


def _known_revision(revision: str) -> bool:
    """True when this code's migration tree contains the revision."""
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_ALEMBIC_INI.parent / "nexctf/alembic"))
    try:
        return ScriptDirectory.from_config(cfg).get_revision(revision) is not None
    except CommandError:
        return False


def key_for(now: datetime, source: BackupSource, revision: str | None = None) -> str:
    """Build a backup key, carrying the source and revision the name can hold."""
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    suffix = f"-{revision}" if revision and _REVISION_RE.fullmatch(revision) else ""
    return f"{PREFIX}nexctf-{stamp}-{source}{suffix}.dump"


def validate_key(key: str) -> str:
    """Allowlist a caller-supplied key: it must be a backup name under ``backups/``."""
    if not key.startswith(PREFIX) or not _KEY_RE.match(key.removeprefix(PREFIX)):
        raise BackupError(f"{key!r} is not a backup key")
    return key


def revision_of(key: str) -> str | None:
    """Read the Alembic revision a backup was taken at out of its key."""
    match = _KEY_RE.match(key.removeprefix(PREFIX))
    return match.group("revision") if match else None


def source_of(key: str) -> BackupSource | None:
    """Read what triggered a backup out of its key. None for pre-source backups."""
    match = _KEY_RE.match(key.removeprefix(PREFIX))
    source = match.group("source") if match else None
    return BackupSource(source) if source else None


async def create(source: BackupSource) -> tuple[str, int]:
    """Dump the database to S3. Returns the object key and its size in bytes."""
    revision = await current_revision()
    key = key_for(datetime.now(UTC), source, revision)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "dump"
        await _run("pg_dump", "-Fc", "--no-owner", "--no-privileges", "-f", str(path))
        size = path.stat().st_size
        await s3.upload_file(key, str(path))

    logger.info("Created backup %s (revision %s, %d bytes)", key, revision, size)
    return key, size


async def restore(key: str) -> None:
    """Replace the database with an archive from S3. The caller stops the app first."""
    validate_key(key)

    revision = revision_of(key)
    if revision and not _known_revision(revision):
        raise BackupError(
            f"Backup was taken at Alembic revision {revision}, which this version of "
            "NexCTF does not know. Upgrade NexCTF before restoring it."
        )

    safety_key, _ = await create(BackupSource.PRE_RESTORE)
    logger.info("Pre-restore backup of the current database: %s", safety_key)

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "dump")
        await s3.download_file(key, path)
        await _run(
            "pg_restore",
            "--clean",
            "--if-exists",
            "--single-transaction",
            "--no-owner",
            "--no-privileges",
            path,
        )

    logger.info("Restored backup %s", key)


async def listing() -> list[dict]:
    """Every backup in S3, newest first, with the revision read from its key."""
    objects = [
        obj
        for obj in await s3.list_prefix(PREFIX)
        if _KEY_RE.match(obj["Key"].removeprefix(PREFIX))
    ]
    objects.sort(key=lambda o: o["LastModified"], reverse=True)
    return [
        {
            "key": obj["Key"],
            "size": obj["Size"],
            "created_at": obj["LastModified"],
            "revision": revision_of(obj["Key"]),
            "source": source_of(obj["Key"]),
        }
        for obj in objects
    ]


async def prune(keep_last: int) -> int:
    """Delete all but the newest ``keep_last`` routine dumps."""
    if keep_last < 1:
        return 0
    routine = [
        obj for obj in await listing() if obj["source"] is not BackupSource.PRE_RESTORE
    ]
    stale = routine[keep_last:]
    for backup in stale:
        await s3.delete(backup["key"])
    return len(stale)
