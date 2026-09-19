"""Instance <-> bundle binding: export, plan and apply."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from nexctf.bundle.diff import Action, EntityKind
from nexctf.core import s3
from nexctf.core.appconfig import ConfigType, all_defs
from nexctf.model import (
    Challenge,
    ConfigEntry,
    CustomPage,
    File,
    Hint,
    Link,
    Question,
    Solution,
    Submission,
    Team,
    User,
    UserRole,
)
from nexctf.model.link import Visibility
from nexctf.module import bundle
from nexctf.plugins.builtin.challenge.standard.model import StandardChallenge
from nexctf.plugins.builtin.solution.match.model import MatchSolution
from nexctf.plugins.registry import challenge_registry, solution_registry
from nexctf.schema.challenge import (
    AdminChallengeCreate,
    AdminChallengeRead,
    AdminChallengeUpdate,
)
from nexctf.schema.solution import AdminSolutionRead

ALT_TYPE = "bundle_alt"


class AltChallenge(Challenge):
    """A second challenge type, so a type change has somewhere to go."""

    __tablename__ = "challenges_bundle_alt"
    __mapper_args__ = {"polymorphic_identity": ALT_TYPE}

    id: Mapped[UUID] = mapped_column(ForeignKey("challenges.id"), primary_key=True)


class AltChallengeRead(AdminChallengeRead):
    pass


# Registered at import: the registry is global, and the schema lookups the
# bundle does need the type present before any session is built.
challenge_registry.register(
    ALT_TYPE,
    model=AltChallenge,
    create_schema=AdminChallengeCreate,
    update_schema=AdminChallengeUpdate,
    read_schema=AltChallengeRead,
)


@pytest.fixture
def alt_challenge_type() -> str:
    """The name the throwaway second challenge type is registered under."""
    return ALT_TYPE


@pytest.fixture
async def author(db_session: AsyncSession) -> User:
    user = User(username="bundle_admin", hashed_password="x", role=UserRole.admin)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def content(db_session: AsyncSession, author: User) -> StandardChallenge:
    """One challenge with a question, hint, solution and an attached file."""
    file = File(
        id=uuid4(),
        name="handout",
        s3_key="",
        original_filename="handout.txt",
        mime_type="text/plain",
        file_size=5,
    )
    file.s3_key = f"files/{file.id}"
    db_session.add(file)
    await s3.upload(file.s3_key, b"hello", "text/plain")

    challenge = StandardChallenge(
        title="Baby Web",
        description="Find the flag",
        is_active=True,
        category="web",
        tags=["easy"],
        author_id=author.id,
    )
    db_session.add(challenge)
    await db_session.flush()

    question = Question(challenge_id=challenge.id, label="Part 1", points=50)
    db_session.add(question)
    await db_session.flush()
    await db_session.refresh(question, ["files"])
    question.files = [file]
    db_session.add(Hint(question_id=question.id, title="Look", content="at the source"))
    db_session.add(MatchSolution(question_id=question.id, value="flag{a}"))

    db_session.add(CustomPage(slug="rules", title="Rules", content="# Rules"))
    db_session.add(
        Link(
            name="Discord",
            url="https://d",
            visibility=Visibility.PUBLIC,
            is_enabled=True,
        )
    )
    db_session.add(ConfigEntry(key="ctf.name", value="My Event"))
    await db_session.flush()
    return challenge


async def test_build_bundle_carries_the_authored_content(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    built, blobs = await bundle.build_bundle(db_session)

    assert [c.title for c in built.challenges] == ["Baby Web"]
    challenge = built.challenges[0]
    assert challenge.id == content.id
    assert challenge.author_username == "bundle_admin"
    assert challenge.questions[0].solutions[0].data == {
        "value": "flag{a}",
        "case_sensitive": False,
    }
    assert built.config["ctf.name"] == "My Event"
    assert [p.slug for p in built.pages] == ["rules"]
    assert list(blobs.values()) == [b"hello"]


async def test_the_manifest_records_what_the_bundle_needs(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    built, _ = await bundle.build_bundle(db_session, include_files=False)
    assert built.manifest.requires.challenge_types == ["standard"]
    assert built.manifest.requires.solve_types == ["match"]


def _a_secret_key() -> str:
    return next(
        key for key, def_ in all_defs().items() if def_.type is ConfigType.SECRET
    )


async def test_secret_config_stays_behind_unless_it_is_asked_for(
    db_session: AsyncSession,
) -> None:
    secret = _a_secret_key()
    db_session.add(ConfigEntry(key=secret, value="hunter2"))
    await db_session.flush()

    built, _ = await bundle.build_bundle(db_session, include_files=False)
    assert secret not in built.config


async def test_secret_config_travels_when_it_is_asked_for(
    db_session: AsyncSession,
) -> None:
    secret = _a_secret_key()
    db_session.add(ConfigEntry(key=secret, value="hunter2"))
    await db_session.flush()

    built, _ = await bundle.build_bundle(
        db_session, include_files=False, include_secrets=True
    )
    assert built.config[secret] == "hunter2"


async def test_an_unchanged_secret_does_not_plan_as_a_change(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    """The current side is compared with secrets, or every secret reads as new."""
    secret = _a_secret_key()
    db_session.add(ConfigEntry(key=secret, value="hunter2"))
    await db_session.flush()
    built, blobs = await bundle.build_bundle(db_session, include_secrets=True)

    plan = await bundle.plan_import(db_session, built, blobs=blobs)

    entry = next(e for e in plan.entries if e.id == secret)
    assert entry.action is Action.UNCHANGED


async def test_a_changed_secret_plans_without_showing_its_value(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    secret = _a_secret_key()
    db_session.add(ConfigEntry(key=secret, value="old-password"))
    await db_session.flush()
    built, blobs = await bundle.build_bundle(db_session, include_secrets=True)
    built.config[secret] = "new-password"

    plan = await bundle.plan_import(db_session, built, blobs=blobs)

    entry = next(e for e in plan.entries if e.id == secret)
    assert entry.action is Action.UPDATE
    assert entry.changes[secret] == ["***", "***"]
    assert "new-password" not in plan.model_dump_json()


async def test_an_exported_secret_can_be_imported_back(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    secret = _a_secret_key()
    db_session.add(ConfigEntry(key=secret, value="old-password"))
    await db_session.flush()
    built, blobs = await bundle.build_bundle(db_session, include_secrets=True)
    built.config[secret] = "new-password"

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    stored = (
        await db_session.execute(select(ConfigEntry).where(ConfigEntry.key == secret))
    ).scalar_one()
    assert stored.value == "new-password"


async def test_a_bundle_without_secrets_leaves_the_stored_ones_alone(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    """Config absence means leave alone, and an export without secrets is absence."""
    secret = _a_secret_key()
    db_session.add(ConfigEntry(key=secret, value="keep-me"))
    await db_session.flush()
    built, blobs = await bundle.build_bundle(db_session)
    assert secret not in built.config

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    stored = (
        await db_session.execute(select(ConfigEntry).where(ConfigEntry.key == secret))
    ).scalar_one()
    assert stored.value == "keep-me"


async def test_re_importing_an_export_is_a_no_op(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    plan = await bundle.plan_import(db_session, built, blobs=blobs)

    assert plan.applicable() == []
    assert set(plan.counts()) == {"unchanged"}


async def test_an_edit_plans_as_an_update_with_a_field_diff(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    built.challenges[0].questions[0].points = 200

    plan = await bundle.plan_import(db_session, built, blobs=blobs)
    entry = next(e for e in plan.entries if e.kind is EntityKind.QUESTION)
    assert entry.action is Action.UPDATE
    assert entry.changes["points"] == [50, 200]


async def test_toggling_a_challenge_open_plans_as_event_state(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    built.challenges[0].is_active = False

    plan = await bundle.plan_import(db_session, built, blobs=blobs)
    entry = next(e for e in plan.entries if e.kind is EntityKind.CHALLENGE)
    assert entry.action is Action.EVENT_STATE


async def test_a_reused_title_on_another_id_is_a_conflict_not_an_error(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    built.challenges[0].id = uuid4()

    plan = await bundle.plan_import(db_session, built, blobs=blobs)
    entry = next(e for e in plan.entries if e.kind is EntityKind.CHALLENGE)
    assert entry.action is Action.CONFLICT
    assert "title" in (entry.reason or "")


async def test_a_type_change_plans_as_a_destructive_recreate(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    built.challenges[0].questions[0].solutions[0].solve_type = "regex"
    built.challenges[0].questions[0].solutions[0].data = {"pattern": "flag\\{.*\\}"}

    plan = await bundle.plan_import(db_session, built, blobs=blobs)
    entry = next(e for e in plan.entries if e.kind is EntityKind.SOLUTION)
    assert entry.action is Action.RECREATE
    assert "cannot be updated in place" in (entry.reason or "")


async def test_a_delete_is_blocked_while_solves_reference_it(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    team = Team(name="Solvers", invite_code="SOLVERS1")
    db_session.add(team)
    await db_session.flush()
    question = built.challenges[0].questions[0]
    db_session.add(
        Submission(
            team_id=team.id, question_id=question.id, answer="flag{a}", is_correct=True
        )
    )
    await db_session.flush()
    built.challenges = []

    plan = await bundle.plan_import(db_session, built, blobs=blobs, prune=True)
    entry = next(e for e in plan.entries if e.kind is EntityKind.CHALLENGE)
    assert entry.action is Action.BLOCKED
    assert "submission" in (entry.reason or "")


async def test_a_missing_type_fails_the_plan_loudly(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    built.challenges[0].challenge_type = "nonexistent"

    with pytest.raises(bundle.BundleError, match="challenge types nonexistent"):
        await bundle.plan_import(db_session, built, blobs=blobs)


async def test_applying_preserves_ids_and_wires_the_m2m(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    new_challenge_id = uuid4()
    new_question_id = uuid4()
    challenge = built.challenges[0].model_copy(deep=True)
    challenge.id = new_challenge_id
    challenge.title = "Second Challenge"
    challenge.questions[0].id = new_question_id
    challenge.questions[0].hints[0].id = uuid4()
    challenge.questions[0].solutions[0].id = uuid4()
    built.challenges.append(challenge)

    applied = await bundle.apply_import(db_session, mock_redis, built, blobs)

    assert applied.counts()["create"] >= 4
    created = await db_session.get(StandardChallenge, new_challenge_id)
    assert created is not None
    question = await db_session.get(Question, new_question_id)
    assert question is not None
    await db_session.refresh(question, ["files", "solutions"])
    assert [f.id for f in question.files] == list(blobs)
    assert isinstance(question.solutions[0], MatchSolution)


async def test_an_import_resolves_the_author_by_username_and_never_creates_one(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    challenge = built.challenges[0].model_copy(deep=True)
    challenge.id = uuid4()
    challenge.title = "Ghost Authored"
    challenge.author_username = "someone_else"
    challenge.questions = []
    built.challenges.append(challenge)

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    created = await db_session.get(StandardChallenge, challenge.id)
    assert created is not None and created.author_id is None
    users = (await db_session.execute(select(User.username))).scalars().all()
    assert "someone_else" not in users


async def test_every_known_setting_travels_not_just_the_overrides(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    """An author editing a bundle should not have to know the key names."""
    built, _ = await bundle.build_bundle(db_session, include_files=False)

    public = {k for k, d in all_defs().items() if d.type is not ConfigType.SECRET}
    assert set(built.config) == public
    assert built.config["ctf.name"] == "My Event"
    assert built.config["ctf.team_size"] == str(all_defs()["ctf.team_size"].default)


async def test_setting_a_default_valued_key_writes_no_override(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    """Storing a row for a default would pin it against a later default change."""
    built, blobs = await bundle.build_bundle(db_session)
    built.config["ctf.name"] = str(all_defs()["ctf.name"].default)

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    rows = (
        (
            await db_session.execute(
                select(ConfigEntry).where(ConfigEntry.key == "ctf.name")
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


async def test_changing_a_default_valued_key_writes_the_override(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    assert built.config["ctf.team_size"] == str(all_defs()["ctf.team_size"].default)
    built.config["ctf.team_size"] = "9"

    plan = await bundle.plan_import(db_session, built, blobs=blobs)
    entry = next(e for e in plan.entries if e.id == "ctf.team_size")
    assert entry.action is Action.UPDATE

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    stored = (
        await db_session.execute(
            select(ConfigEntry).where(ConfigEntry.key == "ctf.team_size")
        )
    ).scalar_one()
    assert stored.value == "9"


async def test_a_missing_config_key_is_left_alone_unless_pruning(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    built.config.pop("ctf.name")

    plan = await bundle.plan_import(db_session, built, blobs=blobs)
    assert not [e for e in plan.applicable() if e.kind is EntityKind.CONFIG]

    pruning = await bundle.plan_import(db_session, built, blobs=blobs, prune=True)
    entry = next(e for e in pruning.entries if e.id == "ctf.name")
    assert entry.action is Action.DELETE


async def test_every_planned_entry_is_written(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    built.challenges[0].title = "Renamed Challenge"
    built.pages[0].title = "House Rules"

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    page = await db_session.get(CustomPage, built.pages[0].id)
    challenge = await db_session.get(StandardChallenge, content.id)
    assert page is not None and page.title == "House Rules"
    assert challenge is not None and challenge.title == "Renamed Challenge"


async def test_a_data_block_cannot_smuggle_fields_past_the_plan(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    """`data` is the type's own columns only, or the plan stops binding writes.

    The create schemas ignore unknown keys rather than rejecting them, so an
    archive naming a base column here would be written straight onto the model
    while the plan diffed, and displayed, the untouched declared value.
    """
    built, blobs = await bundle.build_bundle(db_session)
    challenge = built.challenges[0]
    challenge.title = "Baby Web"
    challenge.data = {"title": "PWNED", "category": "hijacked"}

    with pytest.raises(bundle.BundleError, match="does not declare"):
        await bundle.plan_import(db_session, built, blobs=blobs)
    with pytest.raises(bundle.BundleError, match="does not declare"):
        await bundle.apply_import(db_session, mock_redis, built, blobs)

    stored = await db_session.get(StandardChallenge, challenge.id)
    assert stored is not None
    await db_session.refresh(stored)
    assert stored.title == "Baby Web"
    assert stored.category == "web"


async def test_a_solution_data_block_is_narrowed_the_same_way(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    solution = built.challenges[0].questions[0].solutions[0]
    solution.data = {**solution.data, "question_id": str(uuid4())}

    with pytest.raises(bundle.BundleError, match="does not declare"):
        await bundle.plan_import(db_session, built, blobs=blobs)


async def test_a_type_s_own_columns_still_travel(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    """The narrowing must not cost a plugin its declared columns."""
    built, blobs = await bundle.build_bundle(db_session)
    solution = built.challenges[0].questions[0].solutions[0]
    assert set(solution.data) == {"value", "case_sensitive"}
    solution.data = {"value": "flag{rotated}", "case_sensitive": True}

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    stored = await db_session.get(MatchSolution, solution.id)
    assert stored is not None
    await db_session.refresh(stored)
    assert stored.value == "flag{rotated}"
    assert stored.case_sensitive is True


def test_safe_data_narrows_independently_of_validation() -> None:
    """The write path carries its own allowlist, not just the plan-time check."""
    narrowed = bundle.safe_data(
        solution_registry,
        "match",
        frozenset(AdminSolutionRead.model_fields),
        {"value": "flag{ok}", "question_id": "smuggled", "id": "smuggled"},
    )
    assert narrowed == {"value": "flag{ok}"}


async def test_a_conflict_refuses_the_whole_import(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    """Apply is atomic: one refused entry stops the changes beside it too."""
    built, blobs = await bundle.build_bundle(db_session)
    built.pages[0].title = "A perfectly good edit"
    built.challenges[0].id = uuid4()  # same title, different id

    with pytest.raises(bundle.BundleError, match="conflict"):
        await bundle.apply_import(db_session, mock_redis, built, blobs)

    page = await db_session.get(CustomPage, built.pages[0].id)
    assert page is not None and page.title == "Rules"


async def test_a_blocked_change_says_how_to_get_past_it(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    """A blocked change is not fixable in the archive, so do not say it is."""
    built, blobs = await bundle.build_bundle(db_session)
    team = Team(name="Solvers", invite_code="SOLVERS3")
    db_session.add(team)
    await db_session.flush()
    question = built.challenges[0].questions[0]
    db_session.add(
        Submission(
            team_id=team.id, question_id=question.id, answer="x", is_correct=True
        )
    )
    await db_session.flush()
    built.challenges = []

    with pytest.raises(bundle.BundleError, match="import without pruning"):
        await bundle.apply_import(db_session, mock_redis, built, blobs, prune=True)


async def test_an_unknown_setting_is_skipped_not_blocking(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    """An archive from a newer build must still import what this one understands."""
    built, blobs = await bundle.build_bundle(db_session)
    built.pages[0].title = "House Rules"
    built.config["plugin.not_installed.thing"] = "1"

    plan = await bundle.plan_import(db_session, built, blobs=blobs)
    entry = next(e for e in plan.entries if e.id == "plugin.not_installed.thing")
    assert entry.action is Action.SKIPPED
    assert not plan.refused()

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    page = await db_session.get(CustomPage, built.pages[0].id)
    assert page is not None and page.title == "House Rules"


async def test_a_child_left_out_of_the_archive_says_it_was_left_alone(
    db_session: AsyncSession, content: StandardChallenge
) -> None:
    """Deleting a hint from question.yaml without pruning must not be silent."""
    built, blobs = await bundle.build_bundle(db_session)
    removed = built.challenges[0].questions[0].hints.pop()

    plan = await bundle.plan_import(db_session, built, blobs=blobs)

    entry = next(e for e in plan.entries if e.id == str(removed.id))
    assert entry.action is Action.SKIPPED
    assert "pruning" in (entry.reason or "")
    assert await db_session.get(Hint, removed.id) is not None


async def test_pruning_removes_what_the_bundle_does_not_carry(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    removed_hint = built.challenges[0].questions[0].hints.pop()
    removed_solution = built.challenges[0].questions[0].solutions.pop()
    built.links = []

    without_pruning = await bundle.plan_import(db_session, built, blobs=blobs)
    assert not [
        entry
        for entry in without_pruning.entries
        if entry.id in {str(removed_hint.id), str(removed_solution.id)}
        and entry.action is Action.DELETE
    ]

    await bundle.apply_import(db_session, mock_redis, built, blobs, prune=True)

    assert await db_session.get(Hint, removed_hint.id) is None
    assert await db_session.get(Solution, removed_solution.id) is None
    assert (await db_session.execute(select(Link))).scalars().all() == []


def test_the_export_filename_carries_the_moment_it_was_built() -> None:
    when = datetime(2026, 9, 19, 14, 30, 5, tzinfo=UTC)
    assert bundle.filename_for(when) == "nexctf-bundle-20260919T143005Z.zip"


def test_an_import_key_must_be_a_staged_uuid_archive() -> None:
    staged = f"{bundle.IMPORT_PREFIX}{uuid4()}.zip"
    assert bundle.validate_import_key(staged) == staged
    with pytest.raises(bundle.BundleError):
        bundle.validate_import_key("imports/../exports/x.zip")


async def test_an_import_emits_one_audit_event_not_one_per_row(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    from nexctf.model import Event

    built, blobs = await bundle.build_bundle(db_session)
    built.challenges[0].title = "Audited"

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    events = (
        (await db_session.execute(select(Event).where(Event.target_type == "bundle")))
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].event_type == "bundle.import"


async def test_solutions_survive_a_recreate(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    solution = built.challenges[0].questions[0].solutions[0]
    solution.solve_type = "regex"
    solution.data = {"pattern": "flag\\{.*\\}"}

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    stored = await db_session.get(Solution, solution.id)
    assert stored is not None and stored.solve_type == "regex"


async def test_recreating_a_challenge_keeps_its_question_tree(
    db_session: AsyncSession,
    content: StandardChallenge,
    alt_challenge_type: str,
    mock_redis,
) -> None:
    """A type change drops the challenge, so its children must plan as creates."""
    built, blobs = await bundle.build_bundle(db_session)
    challenge = built.challenges[0]
    question = challenge.questions[0]
    hint_id, solution_id = question.hints[0].id, question.solutions[0].id
    challenge.challenge_type = alt_challenge_type

    plan = await bundle.plan_import(db_session, built, blobs=blobs)
    assert (
        next(e for e in plan.entries if e.kind is EntityKind.CHALLENGE).action
        is Action.RECREATE
    )
    assert all(
        e.action is Action.CREATE
        for e in plan.entries
        if e.kind in (EntityKind.QUESTION, EntityKind.HINT, EntityKind.SOLUTION)
    )

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    stored = await db_session.get(Question, question.id)
    assert stored is not None and stored.challenge_id == challenge.id
    assert await db_session.get(Hint, hint_id) is not None
    assert await db_session.get(Solution, solution_id) is not None


async def test_a_blocked_challenge_blocks_its_children(
    db_session: AsyncSession, content: StandardChallenge, alt_challenge_type: str
) -> None:
    """Children of an unapplicable parent must not be offered for writing."""
    built, blobs = await bundle.build_bundle(db_session)
    team = Team(name="Solvers", invite_code="SOLVERS2")
    db_session.add(team)
    await db_session.flush()
    question = built.challenges[0].questions[0]
    db_session.add(
        Submission(
            team_id=team.id, question_id=question.id, answer="x", is_correct=True
        )
    )
    await db_session.flush()
    built.challenges[0].challenge_type = alt_challenge_type

    plan = await bundle.plan_import(db_session, built, blobs=blobs)

    assert plan.applicable() == []
    kinds = {EntityKind.CHALLENGE, EntityKind.QUESTION, EntityKind.HINT}
    assert all(e.action is Action.BLOCKED for e in plan.entries if e.kind in kinds)


async def test_detaching_every_file_from_a_question(
    db_session: AsyncSession, content: StandardChallenge, mock_redis
) -> None:
    built, blobs = await bundle.build_bundle(db_session)
    question = built.challenges[0].questions[0]
    question.file_ids = []

    await bundle.apply_import(db_session, mock_redis, built, blobs)

    stored = await db_session.get(Question, question.id)
    assert stored is not None
    await db_session.refresh(stored, ["files"])
    assert stored.files == []
