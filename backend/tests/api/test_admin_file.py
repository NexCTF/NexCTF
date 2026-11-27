"""Admin file uploads, usage tracking and guarded deletes."""

import hashlib

import pytest
from botocore.exceptions import ClientError
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.api.routes.admin.file import redacted
from nexctf.core import s3
from nexctf.core.config import settings
from nexctf.enums import FileUsageKind
from nexctf.model import CustomPage, File, User
from nexctf.model.question import Question, question_files_table
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.schema.file import FileUsage
from tests.base import get_data


async def _upload(c: AsyncClient, name: str, content: bytes) -> dict:
    resp = await c.post(
        "/admin/file",
        data={"name": name},
        files={"upload": (f"{name}.txt", content, "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _challenge(db_session: AsyncSession, **kwargs) -> StandardChallenge:
    challenge = StandardChallenge(title=kwargs.pop("title", "Files"), **kwargs)
    db_session.add(challenge)
    await db_session.flush()
    return challenge


def _view(file_id: str) -> str:
    return f"[f](/api/v1/file/{file_id}/view)"


async def test_upload_lands_in_s3_with_its_size_and_hash(
    admin_client: tuple[AsyncClient, User],
) -> None:
    c, _ = admin_client
    data = await _upload(c, "notes", b"hello world")
    assert data["file_size"] == 11
    assert data["sha256"] == hashlib.sha256(b"hello world").hexdigest()
    assert data["duplicates"] == []
    assert await s3.download(data["s3_key"]) == b"hello world"
    await s3.delete(data["s3_key"])


async def test_an_identical_upload_names_its_duplicates(
    admin_client: tuple[AsyncClient, User],
) -> None:
    c, _ = admin_client
    first = await _upload(c, "one", b"same")
    second = await _upload(c, "two", b"same")
    assert [d["id"] for d in second["duplicates"]] == [first["id"]]
    for f in (first, second):
        await s3.delete(f["s3_key"])


async def test_a_new_version_rehashes_the_file(
    admin_client: tuple[AsyncClient, User],
) -> None:
    c, _ = admin_client
    data = await _upload(c, "notes", b"v1")
    resp = await c.put(
        f"/admin/file/{data['id']}",
        files={"upload": ("notes.txt", b"v2", "text/plain")},
    )
    assert resp.json()["data"]["sha256"] == hashlib.sha256(b"v2").hexdigest()
    await s3.delete(data["s3_key"])


async def test_upload_over_the_limit_is_refused(
    admin_client: tuple[AsyncClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 4)
    c, _ = admin_client
    resp = await c.post(
        "/admin/file",
        data={"name": "big"},
        files={"upload": ("big.bin", b"0123456789", "application/octet-stream")},
    )
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "FILE-413"


class TestUsages:
    async def test_the_list_reports_links_and_text_references(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        linked = await _upload(c, "linked", b"a")
        embedded = await _upload(c, "embedded", b"b")
        await _upload(c, "orphan", b"c")
        challenge = await _challenge(db_session, description=_view(embedded["id"]))
        await c.put(
            f"/admin/challenge/{challenge.id}/files",
            json={"file_ids": [linked["id"]]},
        )
        db_session.add(CustomPage(slug="p", title="Page", content=_view(linked["id"])))
        await db_session.flush()

        items = await get_data(c, "/admin/file?items_per_page=50")
        usages = {
            i["name"]: [(u["kind"], u["label"]) for u in i["usages"]] for i in items
        }

        assert usages == {
            "linked": [("challenge", "Files"), ("page_text", "Page")],
            "embedded": [("challenge_text", "Files")],
            "orphan": [],
        }

    @pytest.mark.parametrize(
        ("usage", "names"),
        [
            ("usage=used", {"linked", "embedded"}),
            ("usage=unused", {"orphan"}),
            ("usage=used&usage=unused", {"linked", "embedded", "orphan"}),
        ],
    )
    async def test_the_usage_filter_counts_text_references(
        self,
        admin_client: tuple[AsyncClient, User],
        db_session: AsyncSession,
        usage: str,
        names: set[str],
    ) -> None:
        c, _ = admin_client
        linked = await _upload(c, "linked", b"a")
        embedded = await _upload(c, "embedded", b"b")
        await _upload(c, "orphan", b"c")
        challenge = await _challenge(db_session)
        db_session.add(
            Question(
                label="Q",
                challenge_id=challenge.id,
                description=_view(embedded["id"]),
            )
        )
        await db_session.flush()
        await c.put(
            f"/admin/challenge/{challenge.id}/files",
            json={"file_ids": [linked["id"]]},
        )

        resp = await c.get(f"/admin/file?{usage}")

        assert {i["name"] for i in resp.json()["data"]} == names
        assert resp.json()["filter_attributes"]["usage"] == ["used", "unused"]

    async def test_the_challenge_filter_keeps_its_files(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        mine = await _upload(c, "mine", b"a")
        await _upload(c, "other", b"b")
        challenge = await _challenge(db_session)
        question = Question(label="Q", challenge_id=challenge.id)
        db_session.add(question)
        await db_session.flush()
        await c.put(
            f"/admin/question/{question.id}",
            json={"id": str(question.id), "files_ids": [mine["id"]]},
        )

        resp = await c.get(f"/admin/file?challenge_id={challenge.id}")

        assert [i["name"] for i in resp.json()["data"]] == ["mine"]

    async def test_the_mime_prefix_keeps_matching_types(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        await _upload(c, "notes", b"a")
        resp = await c.post(
            "/admin/file",
            data={"name": "logo"},
            files={"upload": ("logo.png", b"png", "image/png")},
        )
        assert resp.status_code == 201

        found = await get_data(c, "/admin/file?mime_prefix=image/")

        assert [i["name"] for i in found] == ["logo"]

    async def test_the_summary_counts_unused_files(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        used = await _upload(c, "used", b"abc")
        await _upload(c, "orphan", b"de")
        await _challenge(db_session, writeup=_view(used["id"]))

        data = await get_data(c, "/admin/file/summary")

        assert data == {"count": 2, "total_size": 5, "unused_count": 1}


class TestDelete:
    async def test_a_used_file_is_refused_and_kept(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        data = await _upload(c, "linked", b"keep")
        challenge = await _challenge(db_session)
        await c.put(
            f"/admin/challenge/{challenge.id}/files", json={"file_ids": [data["id"]]}
        )

        resp = await c.delete(f"/admin/file/{data['id']}")

        assert resp.status_code == 409
        assert resp.json()["error_code"] == "FILE-409-IN-USE"
        assert resp.json()["data"][0]["kind"] == "challenge"
        assert await s3.download(data["s3_key"]) == b"keep"
        await s3.delete(data["s3_key"])

    async def test_force_unlinks_then_deletes(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        c, _ = admin_client
        data = await _upload(c, "linked", b"gone")
        challenge = await _challenge(db_session)
        question = Question(label="Q", challenge_id=challenge.id)
        db_session.add(question)
        await db_session.flush()
        await c.put(
            f"/admin/question/{question.id}",
            json={"id": str(question.id), "files_ids": [data["id"]]},
        )
        await c.put(
            f"/admin/challenge/{challenge.id}/files", json={"file_ids": [data["id"]]}
        )

        resp = await c.delete(f"/admin/file/{data['id']}?force=true")

        assert resp.status_code == 200, resp.text
        assert (
            await db_session.scalar(select(File).where(File.id == data["id"])) is None
        )
        assert (await db_session.execute(select(question_files_table))).all() == []
        with pytest.raises(ClientError):
            await s3.download(data["s3_key"])

    async def test_an_uppercase_text_reference_still_blocks_delete(
        self, admin_client: tuple[AsyncClient, User], db_session: AsyncSession
    ) -> None:
        """A link typed with uppercase hex counts, as it does in the file list."""
        c, _ = admin_client
        data = await _upload(c, "shouted", b"keep")
        db_session.add(
            CustomPage(slug="up", title="Page", content=_view(data["id"].upper()))
        )
        await db_session.flush()

        resp = await c.delete(f"/admin/file/{data['id']}")

        assert resp.status_code == 409
        assert resp.json()["data"][0]["kind"] == "page_text"
        await s3.delete(data["s3_key"])

    async def test_an_unused_file_deletes_without_force(
        self, admin_client: tuple[AsyncClient, User]
    ) -> None:
        c, _ = admin_client
        data = await _upload(c, "orphan", b"x")
        assert (await c.delete(f"/admin/file/{data['id']}")).status_code == 200


class TestRedaction:
    USAGES = [
        FileUsage(kind=FileUsageKind.CHALLENGE, label="Web 1"),
        FileUsage(kind=FileUsageKind.PAGE_TEXT, label="Draft page"),
        FileUsage(kind=FileUsageKind.CONFIG, label="ctf.logo"),
    ]

    def test_a_challenge_token_sees_only_challenge_labels(self) -> None:
        granted = frozenset(["read:admin.challenge"])
        assert [u.label for u in redacted(self.USAGES, granted)] == [
            "Web 1",
            "***",
            "***",
        ]

    def test_a_session_sees_every_label(self) -> None:
        assert redacted(self.USAGES, None) == self.USAGES
