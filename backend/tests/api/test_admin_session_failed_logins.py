"""Tests for /admin/session/failed-logins, the credential-stuffing pivot."""

from datetime import UTC, datetime, timedelta

from nexctf.model import Event, User
from nexctf.module.session import FAILED_USERNAME_LIMIT, FAILED_USERNAME_MAX

from ..base import ListGuardMixin, get_data, make_user

FAILED_LOGINS = "/admin/session/failed-logins"


async def _add_failure(
    db_session,
    username: str,
    *,
    ip: str | None,
    user: User | None = None,
    hours_ago: float = 0,
    reason: str = "bad_password",
) -> Event:
    row = Event(
        event_type="user.login_failed",
        actor_id=user.id if user else None,
        ip=ip,
        meta={"username": username, "reason": reason},
        created_at=datetime.now(UTC) - timedelta(hours=hours_ago),
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def _overview(client, query: str = "") -> dict:
    return await get_data(client, f"{FAILED_LOGINS}{query}")


async def _addresses(client, query: str = "") -> dict[str, dict]:
    return {row["ip"]: row for row in (await _overview(client, query))["addresses"]}


class TestListFailedLogins(ListGuardMixin):
    PREFIX = FAILED_LOGINS

    async def test_counts_the_usernames_tried_from_one_address(
        self, admin_client, db_session
    ):
        """Many usernames from one address is the stuffing signature."""
        c, _ = admin_client
        for name in ("alice", "bob", "carol"):
            await _add_failure(db_session, name, ip="198.51.100.40")

        sprayed = (await _addresses(c))["198.51.100.40"]

        assert sprayed["username_count"] == 3
        assert sprayed["attempt_count"] == 3
        assert {u["username"] for u in sprayed["usernames"]} == {
            "alice",
            "bob",
            "carol",
        }

    async def test_a_username_that_never_existed_is_still_counted(
        self, admin_client, db_session
    ):
        """The attempted name lives in meta, so unknown accounts are visible."""
        c, _ = admin_client
        await _add_failure(db_session, "root", ip="198.51.100.41")

        tried = (await _addresses(c))["198.51.100.41"]["usernames"][0]

        assert tried["username"] == "root"
        assert tried["user_id"] is None

    async def test_a_username_that_exists_links_its_account(
        self, admin_client, db_session
    ):
        c, _ = admin_client
        alice = await make_user(db_session, "alice")
        await _add_failure(db_session, "alice", ip="198.51.100.42", user=alice)
        await _add_failure(db_session, "ghost", ip="198.51.100.42")

        listed = (await _addresses(c))["198.51.100.42"]
        known = next(u for u in listed["usernames"] if u["username"] == "alice")

        assert known["user_id"] == str(alice.id)
        assert listed["known_username_count"] == 1
        assert listed["username_count"] == 2

    async def test_one_username_counts_once_even_when_the_account_went_away(
        self, admin_client, db_session
    ):
        """Deleting an account nulls the actor, splitting the rows but not the name."""
        c, _ = admin_client
        alice = await make_user(db_session, "alice")
        await _add_failure(
            db_session, "alice", ip="198.51.100.53", user=alice, hours_ago=2
        )
        await _add_failure(db_session, "alice", ip="198.51.100.53")

        listed = (await _addresses(c))["198.51.100.53"]

        assert listed["username_count"] == 1
        assert listed["known_username_count"] == 1
        assert listed["attempt_count"] == 2
        assert [u["username"] for u in listed["usernames"]] == ["alice", "alice"]

    async def test_repeated_attempts_on_one_username_are_one_row(
        self, admin_client, db_session
    ):
        """One account hammered from one address is not a spray."""
        c, _ = admin_client
        for hours in range(4):
            await _add_failure(db_session, "alice", ip="198.51.100.43", hours_ago=hours)

        listed = (await _addresses(c))["198.51.100.43"]

        assert listed["username_count"] == 1
        assert listed["attempt_count"] == 4
        assert listed["usernames"][0]["attempt_count"] == 4

    async def test_the_day_window_excludes_older_attempts(
        self, admin_client, db_session
    ):
        c, _ = admin_client
        await _add_failure(db_session, "alice", ip="198.51.100.44", hours_ago=2)
        await _add_failure(db_session, "bob", ip="198.51.100.45", hours_ago=30)

        day = await _addresses(c, "?window=day")

        assert "198.51.100.44" in day
        assert "198.51.100.45" not in day
        assert "198.51.100.45" in await _addresses(c, "?window=all")

    async def test_live_reads_as_the_last_24_hours(self, admin_client, db_session):
        """Nothing is live about a failed login, so live cannot mean right now."""
        c, _ = admin_client
        await _add_failure(db_session, "alice", ip="198.51.100.46", hours_ago=2)
        await _add_failure(db_session, "bob", ip="198.51.100.47", hours_ago=30)

        live = await _addresses(c, "?window=live")

        assert "198.51.100.46" in live
        assert "198.51.100.47" not in live

    async def test_attempts_without_an_ip_are_ignored(self, admin_client, db_session):
        c, _ = admin_client
        await _add_failure(db_session, "alice", ip=None)

        assert not await _addresses(c)

    async def test_the_most_sprayed_address_comes_first(self, admin_client, db_session):
        c, _ = admin_client
        for name in ("alice", "bob", "carol"):
            await _add_failure(db_session, name, ip="198.51.100.48")
        for _ in range(9):
            await _add_failure(db_session, "alice", ip="198.51.100.49")

        listed = [row["ip"] for row in (await _overview(c))["addresses"]]

        assert listed == ["198.51.100.48", "198.51.100.49"]

    async def test_totals_count_attempts_and_sprayed_addresses(
        self, admin_client, db_session
    ):
        c, _ = admin_client
        for name in ("alice", "bob"):
            await _add_failure(db_session, name, ip="198.51.100.50")
        await _add_failure(db_session, "alice", ip="198.51.100.51")
        await _add_failure(db_session, "alice", ip="198.51.100.51")

        overview = await _overview(c)

        assert overview["attempt_count"] == 4
        assert overview["address_count"] == 2
        assert overview["spray_address_count"] == 1

    async def test_a_successful_login_is_not_a_failure(self, admin_client, db_session):
        c, _ = admin_client
        alice = await make_user(db_session, "alice")
        db_session.add(
            Event(
                event_type="user.login",
                actor_id=alice.id,
                ip="198.51.100.52",
                meta={"username": "alice"},
            )
        )
        await db_session.flush()

        assert "198.51.100.52" not in await _addresses(c, "?window=all")

    async def test_the_listed_usernames_are_capped_but_the_counts_are_not(
        self, admin_client, db_session
    ):
        c, _ = admin_client
        for i in range(FAILED_USERNAME_LIMIT + 5):
            await _add_failure(db_session, f"guess{i}", ip="198.51.100.60")

        listed = (await _addresses(c))["198.51.100.60"]

        assert len(listed["usernames"]) == FAILED_USERNAME_LIMIT
        assert listed["username_count"] == FAILED_USERNAME_LIMIT + 5
        assert listed["attempt_count"] == FAILED_USERNAME_LIMIT + 5

    async def test_an_existing_account_survives_the_cap(self, admin_client, db_session):
        """Noisy unknown names cannot push a real target off the list."""
        c, _ = admin_client
        alice = await make_user(db_session, "alice")
        await _add_failure(db_session, "alice", ip="198.51.100.61", user=alice)
        for i in range(FAILED_USERNAME_LIMIT + 5):
            for _ in range(3):
                await _add_failure(db_session, f"guess{i}", ip="198.51.100.61")

        listed = (await _addresses(c))["198.51.100.61"]

        assert listed["usernames"][0]["user_id"] == str(alice.id)
        assert listed["known_username_count"] == 1

    async def test_a_long_username_is_cut(self, admin_client, db_session):
        c, _ = admin_client
        await _add_failure(db_session, "x" * 5000, ip="198.51.100.62")

        listed = (await _addresses(c))["198.51.100.62"]

        assert listed["usernames"][0]["username"] == "x" * FAILED_USERNAME_MAX
