"""Users, teams, challenges, submissions and solves stored in the database."""

from __future__ import annotations

from datetime import UTC, datetime

from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, Metric
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexctf.model import (
    Challenge,
    Event,
    HintUnlock,
    Submission,
    Team,
    User,
    UserRole,
    UserSession,
)
from nexctf.module.session import FAILED_LOGIN_EVENT
from nexctf.module.stats import get_all_challenge_stats
from nexctf.util.sql import count_of


async def _counts(session: AsyncSession) -> dict[str, int]:
    """Every plain row count, fetched in one round-trip."""
    queries = {
        **{
            f"users_{role.value}": count_of(User, User.role == role)
            for role in UserRole
        },
        "teams": count_of(Team),
        "challenges_true": count_of(Challenge, Challenge.is_active.is_(True)),
        "challenges_false": count_of(Challenge, Challenge.is_active.is_(False)),
        "submissions_true": count_of(Submission, Submission.is_correct.is_(True)),
        "submissions_false": count_of(Submission, Submission.is_correct.is_(False)),
        "hint_unlocks": count_of(HintUnlock),
        "sessions": count_of(UserSession, UserSession.expires_at > datetime.now(UTC)),
    }
    row = await session.execute(
        select(*(query.label(name) for name, query in queries.items()))
    )
    return dict(row.one()._mapping)


async def _login_failures(session: AsyncSession) -> Metric:
    """Failed sign-ins recorded in the audit log, by reason."""
    reason = Event.meta["reason"].astext
    rows = await session.execute(
        select(reason, func.count())
        .where(Event.event_type == FAILED_LOGIN_EVENT)
        .group_by(reason)
    )
    failures = CounterMetricFamily(
        "nexctf_login_failures", "Failed sign-in attempts.", labels=["reason"]
    )
    for value, count in sorted(rows, key=lambda row: row[0] or ""):
        failures.add_metric([value or ""], count)
    return failures


async def _solves(session: AsyncSession, redis: Redis) -> Metric:
    """Teams that solved each challenge."""
    solves = GaugeMetricFamily(
        "nexctf_challenge_solves",
        "Teams that solved each challenge.",
        labels=["challenge", "category"],
    )
    for stats in await get_all_challenge_stats(session, redis):
        solves.add_metric(
            [stats.challenge_title, stats.category or ""], stats.teams_solved
        )
    return solves


async def domain_metrics(session: AsyncSession, redis: Redis) -> list[Metric]:
    """Users, teams, challenges, submissions, solves, hints, sessions and logins."""
    counts = await _counts(session)

    users = GaugeMetricFamily("nexctf_users", "Registered users.", labels=["role"])
    for role in UserRole:
        users.add_metric([role.value], counts[f"users_{role.value}"])

    challenges = GaugeMetricFamily(
        "nexctf_challenges", "Challenges.", labels=["active"]
    )
    submissions = CounterMetricFamily(
        "nexctf_submissions", "Flag submissions.", labels=["correct"]
    )
    for value in ("true", "false"):
        challenges.add_metric([value], counts[f"challenges_{value}"])
        submissions.add_metric([value], counts[f"submissions_{value}"])

    return [
        users,
        GaugeMetricFamily("nexctf_teams", "Registered teams.", value=counts["teams"]),
        challenges,
        submissions,
        await _solves(session, redis),
        CounterMetricFamily(
            "nexctf_hint_unlocks",
            "Hints unlocked by teams.",
            value=counts["hint_unlocks"],
        ),
        GaugeMetricFamily(
            "nexctf_active_sessions",
            "Signed-in browser sessions that have not expired.",
            value=counts["sessions"],
        ),
        await _login_failures(session),
    ]
