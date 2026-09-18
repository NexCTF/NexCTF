"""Tests for /admin/session/addresses, the address-to-accounts pivot."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nexctf.model import Event, Team, User, UserSession

from ..base import ListGuardMixin

ADDRESSES = "/admin/session/addresses"


async def _make_user(db_session, username: str, team: Team | None = None) -> User:
    user = User(username=username, team_id=team.id if team else None)
    db_session.add(user)
    await db_session.flush()
    return user


async def _make_team(db_session, name: str) -> Team:
    team = Team(name=name, invite_code=name.upper()[:8].ljust(8, "0"))
    db_session.add(team)
    await db_session.flush()
    return team


async def _add_session(
    db_session,
    user: User,
    *,
    ip: str | None,
    last_ip: str | None = None,
    minutes_ago: int = 0,
) -> UserSession:
    now = datetime.now(UTC)
    row = UserSession(
        user_id=user.id,
        sid_hash=uuid4().hex,
        ip=ip,
        last_ip=last_ip if last_ip is not None else ip,
        user_agent="Mozilla/5.0",
        last_seen_at=now - timedelta(minutes=minutes_ago),
        expires_at=now + timedelta(hours=1),
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def _add_login(
    db_session, user: User, *, ip: str | None, hours_ago: float = 0
) -> Event:
    row = Event(
        event_type="user.login",
        actor_id=user.id,
        ip=ip,
        meta={"username": user.username},
        created_at=datetime.now(UTC) - timedelta(hours=hours_ago),
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def _overview(client, query: str = "") -> dict:
    resp = await client.get(f"{ADDRESSES}{query}")
    assert resp.status_code == 200
    return resp.json()["data"]


async def _addresses(client, query: str = "") -> dict[str, dict]:
    return {row["ip"]: row for row in (await _overview(client, query))["addresses"]}


class TestListSessionAddresses(ListGuardMixin):
    PREFIX = ADDRESSES

    async def test_groups_accounts_sharing_an_address(self, admin_client, db_session):
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        bob = await _make_user(db_session, "bob")
        await _add_session(db_session, alice, ip="198.51.100.7", minutes_ago=5)
        await _add_session(db_session, bob, ip="198.51.100.7")

        rows = await _addresses(c)

        shared = rows["198.51.100.7"]
        assert shared["account_count"] == 2
        assert shared["session_count"] == 2
        assert [a["username"] for a in shared["accounts"]] == ["bob", "alice"]

    async def test_one_account_on_many_devices_is_one_account(
        self, admin_client, db_session
    ):
        """Several sessions for one user must not read as several accounts."""
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        for _ in range(3):
            await _add_session(db_session, alice, ip="198.51.100.8")

        listed = (await _addresses(c))["198.51.100.8"]

        assert listed["account_count"] == 1
        assert listed["session_count"] == 3
        # One account shares an address with nobody, whatever team it is on.
        assert listed["same_team"] is False

    async def test_addresses_without_an_ip_are_ignored(self, admin_client, db_session):
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        bob = await _make_user(db_session, "bob")
        await _add_session(db_session, alice, ip=None)
        await _add_session(db_session, bob, ip=None)

        listed = await _addresses(c)

        assert None not in listed
        assert not [
            a
            for row in listed.values()
            for a in row["accounts"]
            if a["username"] in ("alice", "bob")
        ]

    async def test_a_replayed_cookie_groups_on_its_current_address(
        self, admin_client, db_session
    ):
        """A session used from elsewhere counts toward that address too."""
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        bob = await _make_user(db_session, "bob")
        await _add_session(
            db_session, alice, ip="198.51.100.1", last_ip="203.0.113.9", minutes_ago=5
        )
        await _add_session(db_session, bob, ip="203.0.113.9")

        shared = (await _addresses(c))["203.0.113.9"]

        assert shared["account_count"] == 2
        moved = next(a for a in shared["accounts"] if a["username"] == "alice")
        assert moved["opened_here"] is False

    async def test_same_team_sharing_is_flagged(self, admin_client, db_session):
        c, _ = admin_client
        team = await _make_team(db_session, "MyTeam")
        alice = await _make_user(db_session, "alice", team)
        bob = await _make_user(db_session, "bob", team)
        await _add_session(db_session, alice, ip="198.51.100.2")
        await _add_session(db_session, bob, ip="198.51.100.2")

        shared = (await _addresses(c))["198.51.100.2"]

        assert shared["same_team"] is True
        assert {a["team_name"] for a in shared["accounts"]} == {"MyTeam"}

    async def test_cross_team_sharing_counts_both_teams(self, admin_client, db_session):
        c, _ = admin_client
        alice = await _make_user(
            db_session, "alice", await _make_team(db_session, "Red")
        )
        bob = await _make_user(db_session, "bob", await _make_team(db_session, "Blue"))
        await _add_session(db_session, alice, ip="198.51.100.9")
        await _add_session(db_session, bob, ip="198.51.100.9")

        shared = (await _addresses(c))["198.51.100.9"]

        assert shared["same_team"] is False
        assert shared["team_count"] == 2

    async def test_teamless_accounts_are_listed_and_never_same_team(
        self, admin_client, db_session
    ):
        c, _ = admin_client
        team = await _make_team(db_session, "MyTeam")
        alice = await _make_user(db_session, "alice", team)
        nomad = await _make_user(db_session, "nomad")
        await _add_session(db_session, alice, ip="198.51.100.3")
        await _add_session(db_session, nomad, ip="198.51.100.3")

        shared = (await _addresses(c))["198.51.100.3"]

        assert shared["same_team"] is False
        assert shared["team_count"] == 1
        assert {a["username"] for a in shared["accounts"]} == {"alice", "nomad"}
        assert any(a["team_id"] is None for a in shared["accounts"])

    async def test_two_teamless_accounts_are_on_no_team_not_two_teams(
        self, admin_client, db_session
    ):
        """Teamless accounts must not read as a cross-team pair."""
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        bob = await _make_user(db_session, "bob")
        await _add_session(db_session, alice, ip="198.51.100.10")
        await _add_session(db_session, bob, ip="198.51.100.10")

        shared = (await _addresses(c))["198.51.100.10"]

        assert shared["same_team"] is False
        assert shared["team_count"] == 0

    async def test_expired_sessions_are_excluded(self, admin_client, db_session):
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        bob = await _make_user(db_session, "bob")
        stale = await _add_session(db_session, alice, ip="198.51.100.4")
        stale.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await _add_session(db_session, bob, ip="198.51.100.4")
        await db_session.flush()

        listed = (await _addresses(c))["198.51.100.4"]

        assert [a["username"] for a in listed["accounts"]] == ["bob"]

    async def test_most_shared_address_comes_first(self, admin_client, db_session):
        c, _ = admin_client
        users = [await _make_user(db_session, f"u{n}") for n in range(3)]
        for user in users:
            await _add_session(db_session, user, ip="198.51.100.5")
        for user in users[:2]:
            await _add_session(db_session, user, ip="198.51.100.6")

        listed = [
            row["ip"]
            for row in (await _overview(c))["addresses"]
            if row["ip"].startswith("198.51.100.")
        ]

        assert listed == ["198.51.100.5", "198.51.100.6"]

    async def test_totals_summarise_every_live_session(self, admin_client, db_session):
        """The summary counts sessions and accounts, not the addresses listed."""
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        bob = await _make_user(db_session, "bob")
        await _add_session(db_session, alice, ip="198.51.100.11")
        await _add_session(db_session, bob, ip="198.51.100.11")
        await _add_session(db_session, alice, ip="198.51.100.12")

        overview = await _overview(c)

        # The admin's own login session rides along, hence the offsets.
        assert overview["session_count"] == 4
        assert overview["account_count"] == 3
        assert overview["address_count"] == 3
        assert overview["shared_address_count"] == 1
        assert overview["cross_team_address_count"] == 0


class TestLoginWindowAddresses:
    """The historical windows group ``user.login`` events, not live sessions."""

    async def test_groups_accounts_by_the_address_they_signed_in_from(
        self, admin_client, db_session
    ):
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        bob = await _make_user(db_session, "bob")
        await _add_login(db_session, alice, ip="198.51.100.20", hours_ago=2)
        await _add_login(db_session, bob, ip="198.51.100.20")

        shared = (await _addresses(c, "?window=all"))["198.51.100.20"]

        assert shared["account_count"] == 2
        assert [a["username"] for a in shared["accounts"]] == ["bob", "alice"]

    async def test_repeat_logins_from_one_address_are_one_account(
        self, admin_client, db_session
    ):
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        for hours in range(3):
            await _add_login(db_session, alice, ip="198.51.100.21", hours_ago=hours)

        listed = (await _addresses(c, "?window=all"))["198.51.100.21"]

        assert listed["account_count"] == 1
        assert listed["session_count"] == 3
        assert listed["same_team"] is False

    async def test_day_window_excludes_older_logins(self, admin_client, db_session):
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        await _add_login(db_session, alice, ip="198.51.100.22", hours_ago=2)
        await _add_login(db_session, alice, ip="198.51.100.23", hours_ago=30)

        listed = await _addresses(c, "?window=day")

        assert "198.51.100.22" in listed
        assert "198.51.100.23" not in listed
        assert "198.51.100.23" in await _addresses(c, "?window=all")

    async def test_an_account_with_no_live_session_is_only_visible_historically(
        self, admin_client, db_session
    ):
        """The gap the live view leaves: signed in this morning, gone since."""
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        await _add_login(db_session, alice, ip="198.51.100.24", hours_ago=4)

        assert "198.51.100.24" not in await _addresses(c)
        assert "198.51.100.24" in await _addresses(c, "?window=all")

    async def test_login_rows_carry_no_device_and_never_moved(
        self, admin_client, db_session
    ):
        """An event records one address and no user agent, so it claims neither."""
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        await _add_login(db_session, alice, ip="198.51.100.25")

        account = (await _addresses(c, "?window=all"))["198.51.100.25"]["accounts"][0]

        assert account["user_agent"] is None
        assert account["opened_here"] is True

    async def test_logins_without_an_ip_are_ignored(self, admin_client, db_session):
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        await _add_login(db_session, alice, ip=None)

        listed = await _addresses(c, "?window=all")

        assert None not in listed
        assert not [
            a
            for row in listed.values()
            for a in row["accounts"]
            if a["username"] == "alice"
        ]

    async def test_widening_the_window_widens_the_totals(
        self, admin_client, db_session
    ):
        """Totals follow the window, so the strip cannot outrun the listing."""
        c, _ = admin_client
        alice = await _make_user(db_session, "alice")
        await _add_login(db_session, alice, ip="198.51.100.26", hours_ago=2)
        await _add_login(db_session, alice, ip="198.51.100.27", hours_ago=30)

        day = await _overview(c, "?window=day")
        every = await _overview(c, "?window=all")

        assert every["address_count"] == day["address_count"] + 1
        assert every["session_count"] == day["session_count"] + 1

    async def test_teams_on_a_past_address_are_the_teams_held_now(
        self, admin_client, db_session
    ):
        c, _ = admin_client
        alice = await _make_user(
            db_session, "alice", await _make_team(db_session, "Red")
        )
        bob = await _make_user(db_session, "bob", await _make_team(db_session, "Blue"))
        await _add_login(db_session, alice, ip="198.51.100.28")
        await _add_login(db_session, bob, ip="198.51.100.28")

        shared = (await _addresses(c, "?window=all"))["198.51.100.28"]

        assert shared["team_count"] == 2
        assert shared["same_team"] is False

    async def test_a_deleted_account_leaves_its_logins_out(
        self, admin_client, db_session
    ):
        """A deleted user nulls the actor on its events, so they group under nobody."""
        c, _ = admin_client
        orphan = Event(
            event_type="user.login",
            actor_id=None,
            ip="198.51.100.29",
            created_at=datetime.now(UTC),
        )
        db_session.add(orphan)
        await db_session.flush()

        assert "198.51.100.29" not in await _addresses(c, "?window=all")

    async def test_an_unknown_window_is_rejected(self, admin_client):
        c, _ = admin_client

        assert (await c.get(f"{ADDRESSES}?window=yesterday")).status_code == 422
