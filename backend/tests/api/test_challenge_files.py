"""Challenge-level file links and the player download route."""

from urllib.parse import urlparse
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.bundle.archive import write_archive
from nexctf.bundle.ir import ChallengeIR
from nexctf.bundle.tree import write_tree
from nexctf.core import s3
from nexctf.model import Event, File, User
from nexctf.model.challenge import challenge_files_table
from nexctf.model.question import Question
from nexctf.module import bundle
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from tests.base import get_data, put_in_team


async def _file(db_session: AsyncSession, name: str) -> File:
    file = File(name=name, s3_key=f"files/{uuid4()}", original_filename=f"{name}.bin")
    db_session.add(file)
    await db_session.flush()
    return file


async def _challenge(db_session: AsyncSession, **kwargs) -> StandardChallenge:
    challenge = StandardChallenge(title="Linked", is_active=True, **kwargs)
    db_session.add(challenge)
    await db_session.flush()
    return challenge


class TestAdminLinks:
    async def test_files_are_set_read_and_audited(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        challenge = await _challenge(db_session)
        b, a = await _file(db_session, "b"), await _file(db_session, "a")

        resp = await c.put(
            f"/admin/challenge/{challenge.id}/files",
            json={"file_ids": [str(b.id), str(a.id)]},
        )

        assert [f["name"] for f in resp.json()["data"]] == ["a", "b"]
        listed = (await c.get(f"/admin/challenge/{challenge.id}/files")).json()
        assert [f["name"] for f in listed["data"]] == ["a", "b"]
        event = await db_session.scalar(
            select(Event).where(Event.event_type == "challenges.updated")
        )
        assert event is not None
        assert event.meta == {"changes": {"files": [[], ["a", "b"]]}}

    async def test_swapping_a_same_named_file_is_audited(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        old, new = (
            await _file(db_session, "chall.zip"),
            await _file(db_session, "chall.zip"),
        )
        challenge = await _challenge(db_session, files=[old])

        await c.put(
            f"/admin/challenge/{challenge.id}/files", json={"file_ids": [str(new.id)]}
        )

        event = await db_session.scalar(
            select(Event).where(Event.event_type == "challenges.updated")
        )
        assert event is not None
        assert event.meta == {"changes": {"files": [["chall.zip"], ["chall.zip"]]}}

    async def test_an_unknown_file_is_refused(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        challenge = await _challenge(db_session)

        resp = await c.put(
            f"/admin/challenge/{challenge.id}/files",
            json={"file_ids": [str(uuid4())]},
        )

        assert resp.status_code == 404
        assert resp.json()["error_code"] == "FILE-404"

    async def test_deleting_the_challenge_keeps_the_file(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        challenge = await _challenge(db_session)
        file = await _file(db_session, "kept")
        await c.put(
            f"/admin/challenge/{challenge.id}/files", json={"file_ids": [str(file.id)]}
        )

        resp = await c.delete(f"/admin/challenge/{challenge.id}")

        assert resp.status_code == 200, resp.text
        assert (await db_session.execute(select(challenge_files_table))).all() == []
        assert await db_session.get(File, file.id) is not None

    async def test_the_bundle_carries_challenge_files(
        self, db_session: AsyncSession
    ) -> None:
        file = await _file(db_session, "carried")
        challenge = await _challenge(db_session, files=[file])

        built, _ = await bundle.build_bundle(db_session, include_files=False)

        [ir] = [ch for ch in built.challenges if ch.id == challenge.id]
        assert ir.file_ids == [file.id]


class TestDownload:
    async def test_a_challenge_file_redirects_to_storage(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = user_client
        file = await _file(db_session, "given")
        challenge = await _challenge(db_session, files=[file])

        detail = await get_data(c, f"/challenges/{challenge.id}")
        [shown] = detail["files"]
        resp = await c.get(shown["url"].removeprefix("/api/v1"), follow_redirects=False)

        assert resp.status_code == 307
        assert file.s3_key in urlparse(resp.headers["location"]).path

    async def test_a_locked_question_file_is_hidden(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, user = user_client
        await put_in_team(db_session, user)
        first, second = (
            await _file(db_session, "first"),
            await _file(db_session, "second"),
        )
        challenge = await _challenge(db_session, sequential=True)
        db_session.add_all(
            [
                Question(label="Q1", index=0, challenge_id=challenge.id, files=[first]),
                Question(
                    label="Q2", index=1, challenge_id=challenge.id, files=[second]
                ),
            ]
        )
        await db_session.flush()
        url = f"/challenges/{challenge.id}/files"

        open_resp = await c.get(f"{url}/{first.id}", follow_redirects=False)
        locked_resp = await c.get(f"{url}/{second.id}", follow_redirects=False)

        assert open_resp.status_code == 307
        assert locked_resp.status_code == 404

    async def test_an_unlinked_or_inactive_file_is_hidden(
        self, user_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = user_client
        stray = await _file(db_session, "stray")
        challenge = await _challenge(db_session)
        hidden = await _file(db_session, "hidden")
        inactive = StandardChallenge(title="Draft", is_active=False, files=[hidden])
        db_session.add(inactive)
        await db_session.flush()

        stray_resp = await c.get(f"/challenges/{challenge.id}/files/{stray.id}")
        draft_resp = await c.get(f"/challenges/{inactive.id}/files/{hidden.id}")

        assert stray_resp.status_code == 404
        assert draft_resp.status_code == 404


async def _plan(c: AsyncClient, archive: bytes) -> dict:
    resp = await c.post(
        "/admin/bundle/import/plan", files={"upload": ("bundle.zip", archive)}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


class TestBundleImport:
    async def test_links_round_trip_and_follow_edits(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        file = await _file(db_session, "kit")
        await s3.upload(file.s3_key, b"kit", None)
        challenge = await _challenge(db_session, files=[file])
        exported = (await c.get("/admin/bundle/export")).content

        unchanged = await _plan(c, exported)
        assert set(unchanged["counts"]) == {"unchanged"}
        await s3.delete(unchanged["import_key"])

        incoming, blobs = bundle.parse_archive(exported)
        [ir] = [ch for ch in incoming.challenges if ch.id == challenge.id]
        ir.file_ids = []
        fresh = uuid4()
        incoming.challenges.append(
            ChallengeIR(
                id=fresh, challenge_type="standard", title="Fresh", file_ids=[file.id]
            )
        )
        plan = await _plan(c, write_archive(write_tree(incoming, blobs)))
        assert plan["counts"].get("update") == 1
        assert plan["counts"].get("create") == 1

        resp = await c.post(
            "/admin/bundle/import/apply", json={"import_key": plan["import_key"]}
        )

        assert resp.status_code == 200, resp.text
        links = (await db_session.execute(select(challenge_files_table))).all()
        assert [(row.challenge_id, row.file_id) for row in links] == [(fresh, file.id)]
        await s3.delete(file.s3_key)
