"""Backup key shape, the restore allowlist and the Alembic revision gate."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from nexctf.core.config import settings
from nexctf.module import backup


def test_key_lives_under_the_backups_prefix() -> None:
    when = datetime(2026, 9, 8, 14, 30, 5, tzinfo=UTC)
    assert backup.key_for(when) == "backups/nexctf-20260908T143005Z.dump"
    assert (
        backup.key_for(when, "16800b9e9b86")
        == "backups/nexctf-20260908T143005Z-16800b9e9b86.dump"
    )


def test_revision_round_trips_through_the_key() -> None:
    """The bundled maxio S3 drops user metadata, so the key has to carry it."""
    key = backup.key_for(datetime.now(UTC), "16800b9e9b86")
    assert backup.revision_of(key) == "16800b9e9b86"
    assert backup.revision_of(backup.key_for(datetime.now(UTC))) is None


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
        key, size = await backup.create()

    assert key.startswith("backups/")
    assert backup.revision_of(key) == "abc123"
    assert size == 50
    assert upload.await_args is not None
    assert upload.await_args.args[0] == key


async def test_prune_keeps_only_the_newest() -> None:
    listing = [{"key": f"backups/b{i}"} for i in range(5)]
    delete = AsyncMock()
    with (
        patch.object(backup, "listing", AsyncMock(return_value=listing)),
        patch.object(backup.s3, "delete", delete),
    ):
        assert await backup.prune(2) == 3

    deleted = [call.args[0] for call in delete.await_args_list]
    assert deleted == ["backups/b2", "backups/b3", "backups/b4"]


def test_pg_password_never_reaches_argv() -> None:
    assert "PGPASSWORD" in backup._pg_env()
    assert not any("PGPASSWORD" in arg for arg in backup._pg_args())


def test_key_drops_a_revision_the_key_syntax_cannot_hold() -> None:
    """A key carrying an unparsable revision would be invisible and unrestorable."""
    key = backup.key_for(datetime(2026, 9, 8, 14, 30, 5, tzinfo=UTC), "rev-with-dash")
    assert key == "backups/nexctf-20260908T143005Z.dump"
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

    async def fake_create() -> tuple[str, int]:
        calls.append("create")
        return "backups/nexctf-20260908T143005Z-abc.dump", 10

    async def fake_run(program: str, *args: str) -> None:
        calls.append(program)

    with (
        patch.object(backup.s3, "download_file", AsyncMock()),
        patch.object(backup, "create", fake_create),
        patch.object(backup, "_run", fake_run),
    ):
        await backup.restore("backups/nexctf-20260908T143005Z.dump")

    assert calls == ["create", "pg_restore"]


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
