"""Bind a content bundle to the instance: DB -> IR, IR -> DB."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectin_polymorphic, selectinload

from nexctf.bundle.archive import read_archive, write_archive
from nexctf.bundle.diff import (
    APPLIED_ACTIONS,
    Action,
    EntityKind,
    Plan,
    PlanEntry,
    diff,
)
from nexctf.bundle.errors import BundleFormatError
from nexctf.bundle.ir import (
    FORMAT_VERSION,
    Bundle,
    ChallengeIR,
    CustomFieldIR,
    FileIR,
    HintIR,
    LinkIR,
    ManifestIR,
    PageIR,
    QuestionIR,
    RequiresIR,
    SolutionIR,
)
from nexctf.bundle.tree import read_tree, write_tree
from nexctf.bundle.yamlio import normalize_long_text
from nexctf.core import appconfig, s3
from nexctf.core.appconfig import REDIS_HASH, ConfigType
from nexctf.enums import InputType
from nexctf.model import (
    Challenge,
    ChallengeFeedback,
    ConfigEntry,
    CustomFieldDefinition,
    CustomFieldTarget,
    CustomFieldType,
    CustomPage,
    File,
    Hint,
    HintUnlock,
    Link,
    Question,
    ScoreAdjustment,
    Solution,
    Submission,
    User,
)
from nexctf.model.link import Visibility
from nexctf.model.question import question_files_table
from nexctf.module.audit import REDACTED, audit_actor
from nexctf.module.challenge.compute import solution_load_option
from nexctf.module.events import emit
from nexctf.plugins.loader import get_plugin_metadata
from nexctf.plugins.registry import (
    PolymorphicRegistry,
    challenge_registry,
    solution_registry,
)
from nexctf.schema.challenge import AdminChallengeRead
from nexctf.schema.solution import AdminSolutionRead

logger = logging.getLogger(__name__)

IMPORT_PREFIX = "imports/"
_IMPORT_KEY_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.zip$"
)
_CHALLENGE_BASE_FIELDS = frozenset(AdminChallengeRead.model_fields)
_SOLUTION_BASE_FIELDS = frozenset(AdminSolutionRead.model_fields)


class BundleError(Exception):
    """A bundle could not be built, planned or applied."""


def nexctf_version() -> str:
    """The running NexCTF version, as the manifest records it."""
    try:
        return importlib.metadata.version("nexctf")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "0.0.0"


def filename_for(now: datetime) -> str:
    """Name the archive the browser saves it under."""
    return f"nexctf-bundle-{now.strftime('%Y%m%dT%H%M%SZ')}.zip"


def validate_import_key(key: str) -> str:
    """Allowlist a staged import key: a bare UUID archive under ``imports/``."""
    if not key.startswith(IMPORT_PREFIX) or not _IMPORT_KEY_RE.match(
        key.removeprefix(IMPORT_PREFIX)
    ):
        raise BundleError(f"{key!r} is not a staged import key")
    return key


def _extra_fields(
    registry: PolymorphicRegistry, type_name: str, base: frozenset[str]
) -> set[str]:
    """The subclass columns a polymorphic type adds beyond its base schema."""
    try:
        entry = registry.get(type_name)
    except KeyError:
        raise BundleError(f"unregistered type {type_name!r}; install its plugin first")
    return set(entry.read_schema.model_fields) - base


def _extras(
    registry: PolymorphicRegistry, type_name: str, instance: Any, base: frozenset[str]
) -> dict[str, Any]:
    """Serialize a polymorphic instance's subclass columns via its read schema."""
    extra = _extra_fields(registry, type_name, base)
    if not extra:
        return {}
    return (
        registry.get(type_name)
        .read_schema.model_validate(instance)
        .model_dump(mode="json", include=extra)
    )


def safe_data(
    registry: PolymorphicRegistry,
    type_name: str,
    base: frozenset[str],
    data: dict[str, Any],
) -> dict[str, Any]:
    """Narrow a bundle's ``data`` block to the columns its type declares."""
    allowed = _extra_fields(registry, type_name, base)
    return {key: value for key, value in data.items() if key in allowed}


def _hint_ir(hint: Hint) -> HintIR:
    return HintIR(
        id=hint.id,
        title=hint.title,
        content=hint.content,
        cost=hint.cost,
        order=hint.order,
    )


def _solution_ir(solution: Solution) -> SolutionIR:
    return SolutionIR(
        id=solution.id,
        solve_type=solution.solve_type,
        data=_extras(
            solution_registry, solution.solve_type, solution, _SOLUTION_BASE_FIELDS
        ),
    )


def _question_ir(question: Question) -> QuestionIR:
    return QuestionIR(
        id=question.id,
        label=question.label,
        description=normalize_long_text(question.description),
        index=question.index,
        points=question.points,
        malus=question.malus,
        input_type=question.input_type.value,
        trap_flags=list(question.trap_flags),
        tags=list(question.tags),
        file_ids=[f.id for f in question.files],
        hints=[_hint_ir(h) for h in question.hints],
        solutions=[_solution_ir(s) for s in question.solutions],
    )


def _challenge_ir(challenge: Challenge) -> ChallengeIR:
    return ChallengeIR(
        id=challenge.id,
        challenge_type=challenge.challenge_type,
        title=challenge.title,
        description=normalize_long_text(challenge.description),
        writeup=normalize_long_text(challenge.writeup),
        is_active=challenge.is_active,
        sequential=challenge.sequential,
        category=challenge.category,
        tags=list(challenge.tags),
        author_username=challenge.author.username if challenge.author else None,
        data=_extras(
            challenge_registry,
            challenge.challenge_type,
            challenge,
            _CHALLENGE_BASE_FIELDS,
        ),
        questions=[_question_ir(q) for q in challenge.questions],
    )


async def _load_challenges(session: AsyncSession) -> list[Challenge]:
    """Every challenge with its questions, hints, solutions, files and subclass rows."""
    options: list[Any] = [
        selectinload(Challenge.questions).selectinload(Question.hints),
        selectinload(Challenge.questions).selectinload(Question.files),
        selectinload(Challenge.questions).options(solution_load_option()),
        joinedload(Challenge.author),
    ]
    if challenge_registry.polymorphic_subclasses:
        options.append(
            selectin_polymorphic(Challenge, challenge_registry.polymorphic_subclasses)
        )
    result = await session.execute(select(Challenge).options(*options))
    return list(result.unique().scalars().all())


async def _config_values(
    session: AsyncSession, *, include_secrets: bool
) -> dict[str, str]:
    """Every setting this build knows, at the value currently in force."""
    defs = appconfig.all_defs()
    rows = await session.execute(select(ConfigEntry.key, ConfigEntry.value))
    stored = {key: value for key, value in rows.all() if key in defs}
    return {
        key: appconfig.effective_raw(key, stored)
        for key, def_ in defs.items()
        if include_secrets or def_.type is not ConfigType.SECRET
    }


async def _file_blobs(files: list[File]) -> dict[UUID, bytes]:
    """Download every file's blob from S3, keyed by file id."""
    return {file.id: await s3.download(file.s3_key) for file in files}


def _requires(bundle_challenges: list[ChallengeIR]) -> RequiresIR:
    """The types and plugins an importing instance must have registered."""
    solve_types = {
        s.solve_type
        for c in bundle_challenges
        for q in c.questions
        for s in q.solutions
    }
    plugins = sorted(
        key for key, meta in get_plugin_metadata().items() if not meta.is_builtin
    )
    return RequiresIR(
        challenge_types=sorted({c.challenge_type for c in bundle_challenges}),
        solve_types=sorted(solve_types),
        plugins=plugins,
    )


async def build_bundle(
    session: AsyncSession,
    *,
    include_files: bool = True,
    include_secrets: bool = False,
) -> tuple[Bundle, dict[UUID, bytes]]:
    """Build the instance's authored content as an IR, with its file blobs."""
    challenges = [_challenge_ir(c) for c in await _load_challenges(session)]

    file_rows = list((await session.execute(select(File))).scalars().all())
    blobs = await _file_blobs(file_rows) if include_files else {}
    files = [
        FileIR(
            id=f.id,
            name=f.name,
            original_filename=f.original_filename,
            mime_type=f.mime_type,
            file_size=f.file_size,
            is_public=f.is_public,
            sha256=hashlib.sha256(blobs[f.id]).hexdigest() if f.id in blobs else None,
        )
        for f in file_rows
    ]

    pages = [
        PageIR(
            id=p.id,
            slug=p.slug,
            title=p.title,
            content=normalize_long_text(p.content) or "",
            is_published=p.is_published,
            nav_placement=p.nav_placement,
        )
        for p in (await session.execute(select(CustomPage))).scalars().all()
    ]
    links = [
        LinkIR(
            id=link.id,
            name=link.name,
            url=link.url,
            visibility=link.visibility.value,
            is_enabled=link.is_enabled,
        )
        for link in (await session.execute(select(Link))).scalars().all()
    ]
    custom_fields = [
        CustomFieldIR(
            id=field.id,
            name=field.name,
            label=field.label,
            field_type=field.field_type.value,
            target=field.target.value,
            is_required=field.is_required,
            is_public=field.is_public,
            is_self_editable=field.is_self_editable,
            show_in_scoreboard=field.show_in_scoreboard,
        )
        for field in (await session.execute(select(CustomFieldDefinition)))
        .scalars()
        .all()
    ]

    bundle = Bundle(
        manifest=ManifestIR(
            format_version=FORMAT_VERSION,
            nexctf_version=nexctf_version(),
            exported_at=datetime.now(UTC),
            requires=_requires(challenges),
        ),
        config=await _config_values(session, include_secrets=include_secrets),
        challenges=challenges,
        files=files,
        pages=pages,
        links=links,
        custom_fields=custom_fields,
    )
    return bundle, blobs


async def export(
    session: AsyncSession,
    *,
    include_files: bool = True,
    include_secrets: bool = False,
) -> bytes:
    """Build the archive and hand it back. Nothing is kept server side."""
    bundle, blobs = await build_bundle(
        session, include_files=include_files, include_secrets=include_secrets
    )
    data = await asyncio.to_thread(lambda: write_archive(write_tree(bundle, blobs)))
    logger.info(
        "Built a content bundle (%d bytes, secrets=%s)", len(data), include_secrets
    )
    return data


def parse_archive(data: bytes) -> tuple[Bundle, dict[UUID, bytes]]:
    """Read an uploaded archive into an IR, refusing an unsupported format."""
    bundle, blobs = read_tree(read_archive(data))
    if bundle.manifest.format_version > FORMAT_VERSION:
        raise BundleFormatError(
            f"bundle format version {bundle.manifest.format_version} is newer than "
            f"this NexCTF build understands ({FORMAT_VERSION}); upgrade NexCTF"
        )
    return bundle, blobs


def check_requirements(bundle: Bundle) -> None:
    """Fail loudly when a type the bundle needs is not in the registry."""
    known_challenge = {name for name, _ in challenge_registry.items()}
    known_solve = {name for name, _ in solution_registry.items()}
    missing_challenge = sorted(
        {c.challenge_type for c in bundle.challenges} - known_challenge
    )
    missing_solve = sorted({s.solve_type for _, s in bundle.solutions()} - known_solve)
    if missing_challenge or missing_solve:
        parts = []
        if missing_challenge:
            parts.append(f"challenge types {', '.join(missing_challenge)}")
        if missing_solve:
            parts.append(f"solve types {', '.join(missing_solve)}")
        raise BundleError(
            f"this instance has no {' and no '.join(parts)}; install the plugins "
            "providing them before importing"
        )


def _reject_unknown_data(
    registry: PolymorphicRegistry,
    type_name: str,
    base: frozenset[str],
    data: dict[str, Any],
    where: str,
) -> None:
    """Refuse a ``data`` block naming anything its type does not declare."""
    unknown = sorted(set(data) - _extra_fields(registry, type_name, base))
    if unknown:
        raise BundleError(
            f"{where}: data carries {', '.join(unknown)}, which {type_name!r} does "
            "not declare. Only a type's own columns may travel in data, so that "
            "the plan shows every field the import would write."
        )


def validate_payloads(bundle: Bundle) -> None:
    """Field-validate the YAML against the registries' create schemas."""
    for challenge in bundle.challenges:
        entry = challenge_registry.get(challenge.challenge_type)
        _reject_unknown_data(
            challenge_registry,
            challenge.challenge_type,
            _CHALLENGE_BASE_FIELDS,
            challenge.data,
            f"challenge {challenge.title!r}",
        )
        payload = {
            "title": challenge.title,
            "description": challenge.description,
            "writeup": challenge.writeup,
            "is_active": challenge.is_active,
            "sequential": challenge.sequential,
            "category": challenge.category,
            "tags": challenge.tags,
            **challenge.data,
        }
        try:
            entry.create_schema.model_validate(payload)
        except ValidationError as exc:
            raise BundleError(f"challenge {challenge.title!r}: {exc}") from exc

    for question, solution in bundle.solutions():
        entry = solution_registry.get(solution.solve_type)
        _reject_unknown_data(
            solution_registry,
            solution.solve_type,
            _SOLUTION_BASE_FIELDS,
            solution.data,
            f"solution {solution.id} on question {question.label!r}",
        )
        try:
            entry.create_schema.model_validate(
                {"question_id": question.id, **solution.data}
            )
        except ValidationError as exc:
            raise BundleError(
                f"solution {solution.id} on question {question.label!r}: {exc}"
            ) from exc


def _ids(
    entries: list[PlanEntry], kind: EntityKind, actions: set[Action]
) -> list[UUID]:
    """Ids of the entries of *kind* whose action is one of *actions*."""
    return [UUID(e.id) for e in entries if e.kind is kind and e.action in actions]


async def _blocked_deletes(
    session: AsyncSession, entries: list[PlanEntry]
) -> dict[tuple[str, str], str]:
    """Reasons the destructive entries cannot be carried out, keyed by plan key."""
    destructive = {Action.DELETE, Action.RECREATE}
    challenge_ids = _ids(entries, EntityKind.CHALLENGE, destructive)
    question_ids = _ids(entries, EntityKind.QUESTION, destructive)
    hint_ids = _ids(entries, EntityKind.HINT, {Action.DELETE})

    blocked: dict[tuple[str, str], str] = {}
    if challenge_ids:
        owned = await session.execute(
            select(Question.challenge_id, func.count(Submission.id))
            .join(Submission, Submission.question_id == Question.id)
            .where(Question.challenge_id.in_(challenge_ids))
            .group_by(Question.challenge_id)
        )
        for challenge_id, count in owned.all():
            blocked[(EntityKind.CHALLENGE.value, str(challenge_id))] = (
                f"{count} submission(s) reference this challenge's questions"
            )
        for model, label in (
            (ChallengeFeedback, "feedback"),
            (ScoreAdjustment, "score adjustment"),
        ):
            rows = await session.execute(
                select(model.challenge_id, func.count(model.id))
                .where(model.challenge_id.in_(challenge_ids))
                .group_by(model.challenge_id)
            )
            for challenge_id, count in rows.all():
                blocked.setdefault(
                    (EntityKind.CHALLENGE.value, str(challenge_id)),
                    f"{count} {label} row(s) reference this challenge",
                )
    if question_ids:
        rows = await session.execute(
            select(Submission.question_id, func.count(Submission.id))
            .where(Submission.question_id.in_(question_ids))
            .group_by(Submission.question_id)
        )
        for question_id, count in rows.all():
            blocked[(EntityKind.QUESTION.value, str(question_id))] = (
                f"{count} submission(s) reference this question"
            )
    if hint_ids:
        rows = await session.execute(
            select(HintUnlock.hint_id, func.count(HintUnlock.id))
            .where(HintUnlock.hint_id.in_(hint_ids))
            .group_by(HintUnlock.hint_id)
        )
        for hint_id, count in rows.all():
            blocked[(EntityKind.HINT.value, str(hint_id))] = (
                f"{count} team(s) unlocked this hint"
            )
    return blocked


async def _fill_hashes(
    session: AsyncSession, current: Bundle, incoming: Bundle
) -> None:
    """Hash the stored blobs the incoming bundle also carries a hash for."""
    wanted = {f.id for f in incoming.files if f.sha256 is not None} & {
        f.id for f in current.files
    }
    if not wanted:
        return
    rows = await session.execute(select(File).where(File.id.in_(wanted)))
    keys = {row.id: row.s3_key for row in rows.scalars().all()}
    for file in current.files:
        key = keys.get(file.id)
        if key is None:
            continue
        async with s3.stream(key) as chunks:
            digest = hashlib.sha256()
            async for chunk in chunks:
                digest.update(chunk)
        file.sha256 = digest.hexdigest()


def _missing_blobs(bundle: Bundle, blobs: dict[UUID, bytes]) -> dict[UUID, str]:
    """Reasons a file entity cannot be written, keyed by file id."""
    return {
        file.id: "the archive carries no blob for this file"
        for file in bundle.files
        if file.id not in blobs
    }


async def plan_import(
    session: AsyncSession,
    incoming: Bundle,
    *,
    blobs: dict[UUID, bytes] | None = None,
    prune: bool = False,
) -> Plan:
    """Diff an incoming bundle against the instance. Writes nothing."""
    check_requirements(incoming)
    validate_payloads(incoming)
    current, _ = await build_bundle(session, include_files=False, include_secrets=True)
    await _fill_hashes(session, current, incoming)
    plan = diff(current, incoming, prune=prune)

    blocked = await _blocked_deletes(session, plan.entries)
    missing = _missing_blobs(incoming, blobs) if blobs is not None else {}
    current_file_ids = {f.id for f in current.files}
    for entry in plan.entries:
        reason = blocked.get(entry.key)
        if reason is not None:
            entry.reason = (
                f"{entry.reason}; {reason}" if entry.reason else reason
            ) + " (delete the solve history first)"
            entry.action = Action.BLOCKED
            continue
        if (
            entry.kind is EntityKind.FILE
            and entry.action is Action.CREATE
            and UUID(entry.id) not in current_file_ids
        ):
            blob_reason = missing.get(UUID(entry.id))
            if blob_reason is not None:
                entry.action = Action.BLOCKED
                entry.reason = blob_reason
    _review_config(plan)
    _cascade_blocked(plan)
    return plan


def _review_config(plan: Plan) -> None:
    """Refuse settings this build cannot write, and mask the ones it must not show."""
    defs = appconfig.all_defs()
    for entry in plan.entries:
        if entry.kind is not EntityKind.CONFIG:
            continue
        def_ = defs.get(entry.id)
        if def_ is None:
            if entry.action in APPLIED_ACTIONS:
                entry.action = Action.SKIPPED
                entry.reason = (
                    "this instance has no such setting; it may come from a newer "
                    "NexCTF or an uninstalled plugin, and is left alone"
                )
            continue
        if def_.type is ConfigType.SECRET:
            entry.changes = {
                field: [None if old is None else REDACTED, REDACTED]
                for field, (old, _) in entry.changes.items()
            }
            if entry.action in APPLIED_ACTIONS and entry.reason is None:
                entry.reason = "a secret setting: the value is not shown"


def _cascade_blocked(plan: Plan) -> None:
    """Block a blocked entity's descendants: their parent row is never written."""
    blocked = {e.id for e in plan.entries if e.action is Action.BLOCKED}
    grew = True
    while grew:
        grew = False
        for entry in plan.entries:
            if entry.parent_id in blocked and entry.action in APPLIED_ACTIONS:
                entry.action = Action.BLOCKED
                entry.reason = entry.reason or "its parent cannot be applied"
                blocked.add(entry.id)
                grew = True


_CHALLENGE_COLUMNS = (
    "title",
    "description",
    "writeup",
    "is_active",
    "sequential",
    "category",
    "tags",
)
_QUESTION_COLUMNS = (
    "label",
    "description",
    "index",
    "points",
    "malus",
    "trap_flags",
    "tags",
)
_HINT_COLUMNS = ("title", "content", "cost", "order")
_FILE_COLUMNS = ("name", "original_filename", "mime_type", "file_size", "is_public")
_PAGE_COLUMNS = ("slug", "title", "content", "is_published", "nav_placement")
_LINK_COLUMNS = ("name", "url", "is_enabled")
_CUSTOM_FIELD_COLUMNS = (
    "name",
    "label",
    "is_required",
    "is_public",
    "is_self_editable",
    "show_in_scoreboard",
)


def _assign(instance: Any, node: Any, columns: tuple[str, ...]) -> None:
    """Copy IR fields onto a mapped instance."""
    for column in columns:
        setattr(instance, column, getattr(node, column))


async def _author_ids(session: AsyncSession, bundle: Bundle) -> dict[str, UUID]:
    """Resolve the bundle's author usernames to local ids. Never creates a user."""
    usernames = {c.author_username for c in bundle.challenges if c.author_username}
    if not usernames:
        return {}
    rows = await session.execute(
        select(User.username, User.id).where(User.username.in_(usernames))
    )
    return {username: user_id for username, user_id in rows.all()}


_SIMPLE_DELETE_MODELS: dict[EntityKind, Any] = {
    EntityKind.PAGE: CustomPage,
    EntityKind.LINK: Link,
    EntityKind.CUSTOM_FIELD: CustomFieldDefinition,
}


class _Writer:
    """Applies one accepted plan inside a single session, then commits once."""

    def __init__(
        self,
        session: AsyncSession,
        bundle: Bundle,
        blobs: dict[UUID, bytes],
        plan: Plan,
    ) -> None:
        self.session = session
        self.bundle = bundle
        self.blobs = blobs
        self.actions = {entry.key: entry.action for entry in plan.applicable()}
        self.deletes: dict[str, set[UUID]] = {}
        for (kind, entity_id), action in self.actions.items():
            if action is Action.DELETE and kind != EntityKind.CONFIG.value:
                self.deletes.setdefault(kind, set()).add(UUID(entity_id))
        self.authors: dict[str, UUID] = {}

    def action_for(self, kind: EntityKind, entity_id: Any) -> Action | None:
        """The accepted action for an entity, or None when it is not being written."""
        return self.actions.get((kind.value, str(entity_id)))

    async def _get(self, model: Any, entity_id: UUID) -> Any:
        return await self.session.get(model, entity_id)

    async def run(self) -> None:
        """Write every accepted entry, children after their parents."""
        self.authors = await _author_ids(self.session, self.bundle)
        await self._flat(
            EntityKind.CUSTOM_FIELD,
            CustomFieldDefinition,
            self.bundle.custom_fields,
            _CUSTOM_FIELD_COLUMNS,
            lambda node: {
                "field_type": CustomFieldType(node.field_type),
                "target": CustomFieldTarget(node.target),
            },
        )
        await self._flat(
            EntityKind.LINK,
            Link,
            self.bundle.links,
            _LINK_COLUMNS,
            lambda node: {"visibility": Visibility(node.visibility)},
        )
        await self._flat(EntityKind.PAGE, CustomPage, self.bundle.pages, _PAGE_COLUMNS)
        await self._files()
        await self._challenges()
        await self._deletes()
        await self.session.flush()

    async def _flat(
        self,
        kind: EntityKind,
        model: Any,
        nodes: list[Any],
        columns: tuple[str, ...],
        enums: Callable[[Any], dict[str, Any]] = lambda node: {},
    ) -> None:
        """Create or update a collection that hangs off nothing else."""
        for node in nodes:
            action = self.action_for(kind, node.id)
            if action is Action.CREATE:
                instance = model(id=node.id, **enums(node))
                _assign(instance, node, columns)
                self.session.add(instance)
            elif action is Action.UPDATE:
                instance = await self._get(model, node.id)
                if instance is not None:
                    _assign(instance, node, columns)
                    for key, value in enums(node).items():
                        setattr(instance, key, value)

    async def _files(self) -> None:
        for file in self.bundle.files:
            action = self.action_for(EntityKind.FILE, file.id)
            if action not in (Action.CREATE, Action.UPDATE):
                continue
            blob = self.blobs.get(file.id)
            if action is Action.CREATE:
                if blob is None:
                    raise BundleError(f"no blob for new file {file.name!r}")
                instance = File(id=file.id, s3_key=f"files/{file.id}")
                _assign(instance, file, _FILE_COLUMNS)
                self.session.add(instance)
            else:
                instance = await self._get(File, file.id)
                if instance is None:
                    continue
                _assign(instance, file, _FILE_COLUMNS)
            if blob is not None:
                await s3.upload(instance.s3_key, blob, file.mime_type)

    async def _challenges(self) -> None:
        for challenge in self.bundle.challenges:
            action = self.action_for(EntityKind.CHALLENGE, challenge.id)
            if action is Action.RECREATE:
                await self._drop_challenge(challenge.id)
                await self.session.flush()
                action = Action.CREATE
            if action is Action.CREATE:
                await self._create_challenge(challenge)
            elif action in (Action.UPDATE, Action.EVENT_STATE):
                await self._update_challenge(challenge)
            await self._questions(challenge)

    async def _create_challenge(self, challenge: ChallengeIR) -> None:
        model = challenge_registry.get(challenge.challenge_type).crud.model
        instance = model(
            id=challenge.id,
            challenge_type=challenge.challenge_type,
            author_id=self.authors.get(challenge.author_username or ""),
            **self._challenge_data(challenge),
        )
        _assign(instance, challenge, _CHALLENGE_COLUMNS)
        self.session.add(instance)

    async def _update_challenge(self, challenge: ChallengeIR) -> None:
        model = challenge_registry.get(challenge.challenge_type).crud.model
        instance = await self._get(model, challenge.id)
        if instance is None:
            return
        _assign(instance, challenge, _CHALLENGE_COLUMNS)
        instance.author_id = self.authors.get(challenge.author_username or "")
        for key, value in self._challenge_data(challenge).items():
            setattr(instance, key, value)

    @staticmethod
    def _challenge_data(challenge: ChallengeIR) -> dict[str, Any]:
        """The challenge's subclass columns, narrowed to what its type declares."""
        return safe_data(
            challenge_registry,
            challenge.challenge_type,
            _CHALLENGE_BASE_FIELDS,
            challenge.data,
        )

    @staticmethod
    def _solution_data(solution: SolutionIR) -> dict[str, Any]:
        """The solution's subclass columns, narrowed to what its type declares."""
        return safe_data(
            solution_registry,
            solution.solve_type,
            _SOLUTION_BASE_FIELDS,
            solution.data,
        )

    async def _questions(self, challenge: ChallengeIR) -> None:
        for question in challenge.questions:
            action = self.action_for(EntityKind.QUESTION, question.id)
            if action is Action.CREATE:
                instance = Question(
                    id=question.id,
                    challenge_id=challenge.id,
                    input_type=InputType(question.input_type),
                )
                _assign(instance, question, _QUESTION_COLUMNS)
                self.session.add(instance)
                await self.session.flush()
            elif action is Action.UPDATE:
                instance = await self._get(Question, question.id)
                if instance is None:
                    continue
                _assign(instance, question, _QUESTION_COLUMNS)
                instance.input_type = InputType(question.input_type)
                instance.challenge_id = challenge.id
            else:
                instance = await self._get(Question, question.id)
                if instance is None:
                    continue
            if action in (Action.CREATE, Action.UPDATE):
                await self._set_files(instance, question)
            await self._hints(question)
            await self._solutions(question)

    async def _set_files(self, question: Any, node: QuestionIR) -> None:
        """Rewrite the ``question_files`` m2m from the bundle's file references."""
        await self.session.refresh(question, ["files"])
        if not node.file_ids:
            question.files = []
            return
        rows = await self.session.execute(
            select(File).where(File.id.in_(node.file_ids))
        )
        question.files = list(rows.scalars().all())

    async def _hints(self, question: QuestionIR) -> None:
        for hint in question.hints:
            action = self.action_for(EntityKind.HINT, hint.id)
            if action is Action.CREATE:
                instance = Hint(id=hint.id, question_id=question.id)
                _assign(instance, hint, _HINT_COLUMNS)
                self.session.add(instance)
            elif action is Action.UPDATE:
                instance = await self._get(Hint, hint.id)
                if instance is not None:
                    _assign(instance, hint, _HINT_COLUMNS)
        for hint_id in self._deleted_ids(
            EntityKind.HINT, {h.id for h in question.hints}
        ):
            instance = await self._get(Hint, hint_id)
            if instance is not None:
                await self.session.delete(instance)

    async def _solutions(self, question: QuestionIR) -> None:
        for solution in question.solutions:
            action = self.action_for(EntityKind.SOLUTION, solution.id)
            if action is Action.RECREATE:
                existing = await self._get(Solution, solution.id)
                if existing is not None:
                    await self.session.delete(existing)
                await self.session.flush()
                action = Action.CREATE
            model = solution_registry.get(solution.solve_type).crud.model
            if action is Action.CREATE:
                self.session.add(
                    model(
                        id=solution.id,
                        question_id=question.id,
                        solve_type=solution.solve_type,
                        **self._solution_data(solution),
                    )
                )
            elif action is Action.UPDATE:
                instance = await self._get(model, solution.id)
                if instance is not None:
                    instance.question_id = question.id
                    for key, value in self._solution_data(solution).items():
                        setattr(instance, key, value)
        for solution_id in self._deleted_ids(
            EntityKind.SOLUTION, {s.id for s in question.solutions}
        ):
            instance = await self._get(Solution, solution_id)
            if instance is not None:
                await self.session.delete(instance)

    def _deleted_ids(self, kind: EntityKind, keep: set[UUID]) -> set[UUID]:
        """Accepted deletes of *kind* that the incoming bundle does not carry."""
        return self.deletes.get(kind.value, set()) - keep

    async def _drop_challenge(self, challenge_id: UUID) -> None:
        """Delete a challenge bottom-up: no FK on questions declares a cascade."""
        questions = (
            (
                await self.session.execute(
                    select(Question)
                    .where(Question.challenge_id == challenge_id)
                    .options(
                        selectinload(Question.hints),
                        selectinload(Question.solutions),
                        selectinload(Question.files),
                    )
                )
            )
            .scalars()
            .all()
        )
        for question in questions:
            await self._drop_question(question)
        challenge = await self._get(Challenge, challenge_id)
        if challenge is not None:
            await self.session.delete(challenge)

    async def _drop_question(self, question: Any) -> None:
        for child in (*question.hints, *question.solutions):
            await self.session.delete(child)
        question.files = []
        await self.session.delete(question)

    async def _deletes(self) -> None:
        """Pruned entities, children before parents, files last."""
        for question_id in self.deletes.get(EntityKind.QUESTION.value, set()):
            question = await self.session.get(
                Question,
                question_id,
                options=[
                    selectinload(Question.hints),
                    selectinload(Question.solutions),
                    selectinload(Question.files),
                ],
            )
            if question is not None:
                await self._drop_question(question)
        await self.session.flush()

        for challenge_id in self.deletes.get(EntityKind.CHALLENGE.value, set()):
            await self._drop_challenge(challenge_id)
        for kind, model in _SIMPLE_DELETE_MODELS.items():
            for entity_id in self.deletes.get(kind.value, set()):
                await self._delete_simple(model, entity_id)
        for file_id in self.deletes.get(EntityKind.FILE.value, set()):
            await self._delete_file(file_id)

    async def _delete_simple(self, model: Any, entity_id: UUID) -> None:
        instance = await self._get(model, entity_id)
        if instance is not None:
            await self.session.delete(instance)

    async def _delete_file(self, file_id: UUID) -> None:
        instance = await self._get(File, file_id)
        if instance is None:
            return
        await self.session.execute(
            question_files_table.delete().where(
                question_files_table.c.file_id == file_id
            )
        )
        await s3.delete(instance.s3_key)
        await self.session.delete(instance)


async def _apply_config(
    session: AsyncSession, bundle: Bundle, actions: dict[tuple[str, str], Action]
) -> tuple[dict[str, str], list[str]]:
    """Stage the accepted config changes. Returns the Redis updates and removals."""
    updates: dict[str, str] = {}
    removals: list[str] = []
    defs = appconfig.all_defs()
    for key, action in (
        (entity_id, action)
        for (kind, entity_id), action in actions.items()
        if kind == EntityKind.CONFIG.value
    ):
        if action is Action.DELETE:
            await _drop_config(session, key)
            removals.append(key)
            continue
        value = bundle.config.get(key)
        if value is None or key not in defs:
            continue
        if value == appconfig.baseline_raw(key):
            await _drop_config(session, key)
            removals.append(key)
            continue
        try:
            await appconfig.stage(session, key, value)
        except ValueError as exc:
            raise BundleError(f"config {key}: {exc}") from exc
        updates[key] = value
    return updates, removals


async def _drop_config(session: AsyncSession, key: str) -> None:
    """Remove a stored override so the key falls back to ENV or the default."""
    entry = (
        await session.execute(select(ConfigEntry).where(ConfigEntry.key == key))
    ).scalar_one_or_none()
    if entry is not None:
        await session.delete(entry)


async def _sync_config_cache(
    redis: Redis | None, updates: dict[str, str], removals: list[str]
) -> None:
    """Mirror the committed config changes into the Redis snapshot."""
    if redis is None or (not updates and not removals):
        return
    pipe = redis.pipeline()
    for key, value in updates.items():
        cast(Any, pipe.hset(REDIS_HASH, key, value))
    if removals:
        cast(Any, pipe.hdel(REDIS_HASH, *removals))
    await cast(Any, pipe.execute())


def _refusal(refused: list[PlanEntry]) -> str:
    """Explain a refusal, pointing at the remedy each kind actually has."""
    conflicts = [e for e in refused if e.action is Action.CONFLICT]
    blocked = [e for e in refused if e.action is Action.BLOCKED]
    parts: list[str] = []
    if conflicts:
        parts.append(
            f"{len(conflicts)} conflict(s), where a title, slug or name already "
            "belongs to a different entity: edit the archive and upload it again"
        )
    if blocked:
        parts.append(
            f"{len(blocked)} blocked change(s), where this instance holds solve "
            "history for something the import would delete: import without "
            "pruning, or delete that history first"
        )
    return "the import was not applied. It has " + "; and ".join(parts) + "."


async def apply_import(
    session: AsyncSession,
    redis: Redis | None,
    incoming: Bundle,
    blobs: dict[UUID, bytes],
    *,
    prune: bool = False,
) -> Plan:
    """Re-derive a plan, then apply every safe entry in one transaction."""
    plan = await plan_import(session, incoming, blobs=blobs, prune=prune)
    if refused := plan.refused():
        raise BundleError(_refusal(refused))
    selected = {entry.key for entry in plan.applicable()}

    writer = _Writer(session, incoming, blobs, plan)
    await writer.run()
    updates, removals = await _apply_config(session, incoming, writer.actions)

    applied = Plan(entries=[e for e in plan.entries if e.key in selected], prune=prune)
    actor_id, ip = audit_actor()
    await emit(
        session,
        event_type="bundle.import",
        actor_id=actor_id,
        ip=ip,
        target_type="bundle",
        target_label=f"{incoming.manifest.nexctf_version} bundle",
        meta={"counts": applied.counts(), "prune": prune},
    )
    await session.commit()
    await _sync_config_cache(redis, updates, removals)
    logger.info("Applied bundle import: %s", applied.counts())
    return applied
