"""Backup key shape, the restore allowlist and the Alembic revision gate."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from nexctf.core.config import settings
from nexctf.module import backup
from nexctf.schema.backup import BackupSource


def test_key_lives_under_the_backups_prefix() -> None:
    when = datetime(2026, 9, 8, 14, 30, 5, tzinfo=UTC)
    assert (
        backup.key_for(when, BackupSource.MANUAL)
        == "backups/nexctf-20260908T143005Z-manual.dump"
    )
    assert (
        backup.key_for(when, BackupSource.AUTO, "16800b9e9b86")
        == "backups/nexctf-20260908T143005Z-auto-16800b9e9b86.dump"
    )


def test_revision_round_trips_through_the_key() -> None:
    """The bundled maxio S3 drops user metadata, so the key has to carry it."""
    now = datetime.now(UTC)
    key = backup.key_for(now, BackupSource.MANUAL, "16800b9e9b86")
    assert backup.revision_of(key) == "16800b9e9b86"
    assert backup.revision_of(backup.key_for(now, BackupSource.MANUAL)) is None


@pytest.mark.parametrize("source", list(BackupSource))
def test_source_round_trips_through_the_key(source: BackupSource) -> None:
    now = datetime.now(UTC)
    assert backup.source_of(backup.key_for(now, source)) is source
    assert backup.source_of(backup.key_for(now, source, "16800b9e9b86")) is source


def test_a_key_predating_sources_still_parses() -> None:
    """Dumps already in S3 must stay listable, restorable and deletable."""
    key = "backups/nexctf-20260908T143005Z-16800b9e9b86.dump"
    assert backup.validate_key(key) == key
    assert backup.source_of(key) is None
    assert backup.revision_of(key) == "16800b9e9b86"


@pytest.mark.parametrize(
    "key",
    [
        "files/secret",
        "backups/../files/secret",
        "backups/nested/dump",
        "backups/",
        "nexctf.dump",
        "backups/evil.sh",
        "backups/nexctf-20260908T143005Z.dump.bak",
    ],
)
async def test_restore_rejects_a_key_outside_backups(key: str) -> None:
    with pytest.raises(backup.BackupError):
        await backup.restore(key)


async def test_restore_rejects_an_unknown_alembic_revision() -> None:
    with pytest.raises(backup.BackupError, match="does not know"):
        await backup.restore("backups/nexctf-20260908T143005Z-deadbeef.dump")


async def test_restore_accepts_a_revision_this_code_knows() -> None:
    revision = "16800b9e9b86"  # the initial migration
    assert backup._known_revision(revision)

    run = AsyncMock()
    with (
        patch.object(backup.s3, "download_file", AsyncMock()),
        patch.object(backup, "create", AsyncMock(return_value=("backups/safety", 1))),
        patch.object(backup, "_run", run),
    ):
        await backup.restore(f"backups/nexctf-20260908T143005Z-{revision}.dump")

    assert run.await_args is not None
    program, *args = run.await_args.args
    assert program == "pg_restore"
    assert "--clean" in args and "--if-exists" in args


async def test_create_uploads_the_dump_stamped_with_the_live_revision() -> None:
    upload = AsyncMock()

    async def fake_pg_dump(program: str, *args: str) -> None:
        Path(args[args.index("-f") + 1]).write_bytes(b"PGDMP" * 10)

    with (
        patch.object(backup, "_run", fake_pg_dump),
        patch.object(backup, "current_revision", AsyncMock(return_value="abc123")),
        patch.object(backup.s3, "upload_file", upload),
    ):
        key, size = await backup.create(BackupSource.MANUAL)

    assert key.startswith("backups/")
    assert backup.revision_of(key) == "abc123"
    assert backup.source_of(key) is BackupSource.MANUAL
    assert size == 50
    assert upload.await_args is not None
    assert upload.await_args.args[0] == key


def _listed(*sources: BackupSource) -> list[dict]:
    return [{"key": f"backups/b{i}", "source": s} for i, s in enumerate(sources)]


async def _prune(listing: list[dict], keep_last: int) -> tuple[int, list[str]]:
    delete = AsyncMock()
    with (
        patch.object(backup, "listing", AsyncMock(return_value=listing)),
        patch.object(backup.s3, "delete", delete),
    ):
        deleted = await backup.prune(keep_last)
    return deleted, [call.args[0] for call in delete.await_args_list]


async def test_prune_keeps_only_the_newest() -> None:
    listing = _listed(*[BackupSource.AUTO] * 5)
    assert await _prune(listing, 2) == (3, ["backups/b2", "backups/b3", "backups/b4"])


async def test_prune_never_deletes_a_pre_restore_copy() -> None:
    """The safety dump is the only way back from a restore of the wrong backup."""
    listing = _listed(
        BackupSource.AUTO,
        BackupSource.PRE_RESTORE,
        BackupSource.MANUAL,
        BackupSource.PRE_RESTORE,
        BackupSource.AUTO,
    )
    assert await _prune(listing, 1) == (2, ["backups/b2", "backups/b4"])


async def test_prune_does_not_count_pre_restore_copies_towards_keep_last() -> None:
    """Restores must not silently shrink how many routine dumps are retained."""
    listing = _listed(
        BackupSource.PRE_RESTORE,
        BackupSource.PRE_RESTORE,
        BackupSource.AUTO,
        BackupSource.AUTO,
    )
    assert await _prune(listing, 2) == (0, [])


async def test_prune_treats_a_backup_taken_before_sources_as_routine() -> None:
    """A sourceless dump is an ordinary one, and the exemption must not widen."""
    listing = _listed(BackupSource.AUTO, BackupSource.AUTO)
    listing.insert(1, {"key": "backups/legacy", "source": None})
    assert await _prune(listing, 1) == (2, ["backups/legacy", "backups/b1"])


def test_pg_password_never_reaches_argv() -> None:
    assert "PGPASSWORD" in backup._pg_env()
    assert not any("PGPASSWORD" in arg for arg in backup._pg_args())


def test_key_drops_a_revision_the_key_syntax_cannot_hold() -> None:
    """A key carrying an unparsable revision would be invisible and unrestorable."""
    key = backup.key_for(
        datetime(2026, 9, 8, 14, 30, 5, tzinfo=UTC),
        BackupSource.MANUAL,
        "rev-with-dash",
    )
    assert key == "backups/nexctf-20260908T143005Z-manual.dump"
    assert backup.validate_key(key) == key


async def test_restore_runs_in_a_single_transaction() -> None:
    """A partial --clean restore would leave the database half old, half new."""
    run = AsyncMock()
    with (
        patch.object(backup.s3, "download_file", AsyncMock()),
        patch.object(backup, "create", AsyncMock(return_value=("backups/safety", 1))),
        patch.object(backup, "_run", run),
    ):
        await backup.restore("backups/nexctf-20260908T143005Z.dump")

    assert run.await_args is not None
    assert "--single-transaction" in run.await_args.args


async def test_run_passes_connection_flags_to_the_binary() -> None:
    """_run prepends them, so no caller repeats them and none can omit them."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(b"", b""))
    proc.returncode = 0
    spawn = AsyncMock(return_value=proc)

    with (
        patch.object(backup.shutil, "which", lambda _: "/usr/bin/pg_dump"),
        patch.object(backup.asyncio, "create_subprocess_exec", spawn),
    ):
        await backup._run("pg_dump", "-Fc")

    assert spawn.await_args is not None
    argv = spawn.await_args.args
    assert argv[0] == "pg_dump"
    for flag in ("-h", "-p", "-U", "-d"):
        assert flag in argv, f"{flag} missing from {argv}"
    assert argv[-1] == "-Fc"
    assert spawn.await_args.kwargs["env"]["PGPASSWORD"] == settings.POSTGRES_PASSWORD


async def test_restore_dumps_the_current_database_first() -> None:
    """The rollback path if a restore turns out to be the wrong one."""
    calls: list[str] = []

    async def fake_create(source: BackupSource) -> tuple[str, int]:
        calls.append(f"create:{source}")
        return "backups/nexctf-20260908T143005Z-pre_restore-abc.dump", 10

    async def fake_run(program: str, *args: str) -> None:
        calls.append(program)

    with (
        patch.object(backup.s3, "download_file", AsyncMock()),
        patch.object(backup, "create", fake_create),
        patch.object(backup, "_run", fake_run),
    ):
        await backup.restore("backups/nexctf-20260908T143005Z.dump")

    assert calls == ["create:pre_restore", "pg_restore"]


async def test_restore_aborts_when_the_safety_dump_fails() -> None:
    """Without a rollback copy the restore must not touch the database."""
    run = AsyncMock()
    with (
        patch.object(backup.s3, "download_file", AsyncMock()),
        patch.object(
            backup, "create", AsyncMock(side_effect=backup.BackupError("no pg_dump"))
        ),
        patch.object(backup, "_run", run),
        pytest.raises(backup.BackupError, match="no pg_dump"),
    ):
        await backup.restore("backups/nexctf-20260908T143005Z.dump")

    run.assert_not_awaited()
