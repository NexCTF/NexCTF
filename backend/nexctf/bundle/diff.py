"""The plan phase: diff an incoming bundle against the current one."""

from __future__ import annotations

import enum
from collections import Counter
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from nexctf.bundle.ir import Bundle, ChallengeIR, QuestionIR

EVENT_STATE_CONFIG = frozenset({"ctf.start_time", "ctf.end_time", "ctf.freeze_time"})


class EntityKind(str, enum.Enum):
    CHALLENGE = "challenge"
    QUESTION = "question"
    HINT = "hint"
    SOLUTION = "solution"
    FILE = "file"
    PAGE = "page"
    LINK = "link"
    CUSTOM_FIELD = "custom_field"
    CONFIG = "config"


class Action(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    EVENT_STATE = "event_state"
    RECREATE = "recreate"
    DELETE = "delete"
    CONFLICT = "conflict"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    UNCHANGED = "unchanged"


APPLIED_ACTIONS = frozenset(
    {Action.CREATE, Action.UPDATE, Action.EVENT_STATE, Action.RECREATE, Action.DELETE}
)
REFUSED_ACTIONS = frozenset({Action.CONFLICT, Action.BLOCKED})


class PlanEntry(BaseModel):
    """One entity's fate under the plan."""

    kind: EntityKind
    id: str
    label: str
    action: Action
    parent_id: str | None = None
    changes: dict[str, list[Any]] = {}
    reason: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        """The accept key: stable across a re-plan of the same archive."""
        return (self.kind.value, self.id)


class Plan(BaseModel):
    """Everything applying a bundle would do, in the order it would happen."""

    entries: list[PlanEntry] = []
    prune: bool = False

    def counts(self) -> dict[str, int]:
        """How many entries fall under each action."""
        return dict(Counter(entry.action.value for entry in self.entries))

    def applicable(self) -> list[PlanEntry]:
        """The entries that would write."""
        return [e for e in self.entries if e.action in APPLIED_ACTIONS]

    def refused(self) -> list[PlanEntry]:
        """The entries blocking the plan."""
        return [e for e in self.entries if e.action in REFUSED_ACTIONS]


_CHALLENGE_FIELDS = [
    "challenge_type",
    "title",
    "description",
    "writeup",
    "is_active",
    "sequential",
    "category",
    "tags",
    "author_username",
    "data",
]
_QUESTION_FIELDS = [
    "label",
    "description",
    "index",
    "points",
    "malus",
    "input_type",
    "trap_flags",
    "tags",
    "file_ids",
]
_HINT_FIELDS = ["title", "content", "cost", "order"]
_SOLUTION_FIELDS = ["solve_type", "data"]
_FILE_FIELDS = [
    "name",
    "original_filename",
    "mime_type",
    "file_size",
    "is_public",
    "sha256",
]
_PAGE_FIELDS = ["slug", "title", "content", "is_published", "nav_placement"]
_LINK_FIELDS = ["name", "url", "visibility", "is_enabled"]
_CUSTOM_FIELD_FIELDS = [
    "name",
    "label",
    "field_type",
    "target",
    "is_required",
    "is_public",
    "is_self_editable",
    "show_in_scoreboard",
]


def _normalized(node: Any, field: str) -> Any:
    """Compare-ready value: lists whose order is not meaningful are sorted."""
    value = getattr(node, field)
    if field in ("tags", "file_ids"):
        return sorted(str(v) for v in value)
    if isinstance(value, UUID):
        return str(value)
    return value


def _field_changes(
    current: Any, incoming: Any, fields: list[str]
) -> dict[str, list[Any]]:
    """``{field: [old, new]}`` for every field whose value differs."""
    changes: dict[str, list[Any]] = {}
    for field in fields:
        old, new = _normalized(current, field), _normalized(incoming, field)
        if old != new:
            changes[field] = [old, new]
    return changes


def _entry(
    kind: EntityKind,
    entity_id: Any,
    label: str,
    action: Action,
    *,
    parent_id: Any = None,
    changes: dict[str, list[Any]] | None = None,
    reason: str | None = None,
) -> PlanEntry:
    return PlanEntry(
        kind=kind,
        id=str(entity_id),
        label=label,
        action=action,
        parent_id=None if parent_id is None else str(parent_id),
        changes=changes or {},
        reason=reason,
    )


def _natural_key_conflict(
    current_by_key: dict[Any, UUID], incoming: Any, key_field: str
) -> str | None:
    """Reason a unique natural key collides with a different row, or None."""
    natural = getattr(incoming, key_field)
    holder = current_by_key.get(natural)
    if holder is not None and holder != incoming.id:
        return (
            f"{key_field} {natural!r} already belongs to another entity "
            f"({holder}); it is unique instance-wide"
        )
    return None


ABSENT_REASON = "the archive does not carry it; turn on pruning to delete it"


def _recreate_reason(field: str, noun: str) -> str:
    """Why a discriminator change forces a delete and a fresh insert."""
    return (
        f"{field} is a polymorphic discriminator and cannot be updated in "
        f"place: the {noun} is deleted and recreated"
    )


def _simple_diff(
    kind: EntityKind,
    current: list[Any],
    incoming: list[Any],
    fields: list[str],
    label: str,
    *,
    prune: bool,
    natural_key: str | None = None,
    announce_absent: bool = False,
    recreate_on: str | None = None,
    noun: str = "row",
    parent_id: Any = None,
) -> list[PlanEntry]:
    """Diff a flat collection by id, with an optional unique natural key."""
    current_index = {item.id: item for item in current}
    incoming_index = {item.id: item for item in incoming}
    by_key = {getattr(i, natural_key): i.id for i in current} if natural_key else {}

    def entry(item: Any, action: Action, **kwargs: Any) -> PlanEntry:
        name = str(getattr(item, label))
        return _entry(kind, item.id, name, action, parent_id=parent_id, **kwargs)

    entries: list[PlanEntry] = []
    for item in incoming:
        conflict = (
            _natural_key_conflict(by_key, item, natural_key) if natural_key else None
        )
        if conflict is not None:
            entries.append(entry(item, Action.CONFLICT, reason=conflict))
            continue
        existing = current_index.get(item.id)
        if existing is None:
            entries.append(entry(item, Action.CREATE))
            continue
        if recreate_on is not None:
            was, now = getattr(existing, recreate_on), getattr(item, recreate_on)
            if was != now:
                entries.append(
                    entry(
                        item,
                        Action.RECREATE,
                        changes={recreate_on: [was, now]},
                        reason=_recreate_reason(recreate_on, noun),
                    )
                )
                continue
        changes = _field_changes(existing, item, fields)
        action = Action.UPDATE if changes else Action.UNCHANGED
        entries.append(entry(item, action, changes=changes))

    for item in current:
        if item.id in incoming_index:
            continue
        if prune:
            entries.append(entry(item, Action.DELETE))
        elif announce_absent:
            entries.append(entry(item, Action.SKIPPED, reason=ABSENT_REASON))
    return entries


def _challenge_entry(current: ChallengeIR | None, incoming: ChallengeIR) -> PlanEntry:
    """Plan a single challenge, treating a type change as a recreate."""
    if current is None:
        return _entry(EntityKind.CHALLENGE, incoming.id, incoming.title, Action.CREATE)
    if current.challenge_type != incoming.challenge_type:
        return _entry(
            EntityKind.CHALLENGE,
            incoming.id,
            incoming.title,
            Action.RECREATE,
            changes={
                "challenge_type": [current.challenge_type, incoming.challenge_type]
            },
            reason=_recreate_reason("challenge_type", "challenge"),
        )
    changes = _field_changes(current, incoming, _CHALLENGE_FIELDS)
    if not changes:
        action = Action.UNCHANGED
    elif "is_active" in changes:
        action = Action.EVENT_STATE
    else:
        action = Action.UPDATE
    return _entry(
        EntityKind.CHALLENGE, incoming.id, incoming.title, action, changes=changes
    )


def _question_entries(
    current_questions: dict[UUID, tuple[ChallengeIR, QuestionIR]],
    challenge: ChallengeIR,
    question: QuestionIR,
    *,
    prune: bool,
) -> list[PlanEntry]:
    """Plan a question with its embedded hints and solutions."""
    found = current_questions.get(question.id)
    if found is None:
        current_question = QuestionIR(id=question.id, label=question.label)
        head = _entry(
            EntityKind.QUESTION,
            question.id,
            question.label,
            Action.CREATE,
            parent_id=challenge.id,
        )
    else:
        current_challenge, current_question = found
        changes = _field_changes(current_question, question, _QUESTION_FIELDS)
        if current_challenge.id != challenge.id:
            changes["challenge_id"] = [str(current_challenge.id), str(challenge.id)]
        head = _entry(
            EntityKind.QUESTION,
            question.id,
            question.label,
            Action.UPDATE if changes else Action.UNCHANGED,
            parent_id=challenge.id,
            changes=changes,
        )

    return [
        head,
        *_simple_diff(
            EntityKind.HINT,
            current_question.hints,
            question.hints,
            _HINT_FIELDS,
            "title",
            prune=prune,
            announce_absent=True,
            parent_id=question.id,
        ),
        *_simple_diff(
            EntityKind.SOLUTION,
            current_question.solutions,
            question.solutions,
            _SOLUTION_FIELDS,
            "solve_type",
            prune=prune,
            announce_absent=True,
            recreate_on="solve_type",
            noun="solution",
            parent_id=question.id,
        ),
    ]


def _config_entries(
    current: dict[str, str], incoming: dict[str, str], *, prune: bool
) -> list[PlanEntry]:
    """Diff the config overrides. A missing key means leave alone unless pruning."""
    entries: list[PlanEntry] = []
    for key in sorted(incoming):
        value = incoming[key]
        old = current.get(key)
        if key in current and old == value:
            entries.append(_entry(EntityKind.CONFIG, key, key, Action.UNCHANGED))
            continue
        if key in EVENT_STATE_CONFIG:
            action = Action.EVENT_STATE
        else:
            action = Action.CREATE if key not in current else Action.UPDATE
        entries.append(
            _entry(EntityKind.CONFIG, key, key, action, changes={key: [old, value]})
        )
    if prune:
        entries += [
            _entry(
                EntityKind.CONFIG,
                key,
                key,
                Action.DELETE,
                changes={key: [current[key], None]},
            )
            for key in sorted(current)
            if key not in incoming
        ]
    return entries


def diff(current: Bundle, incoming: Bundle, *, prune: bool = False) -> Plan:
    """Return what applying *incoming* over *current* would do.

    Args:
        current: The instance's content as it stands.
        incoming: The bundle being imported.
        prune: Whether entities absent from *incoming* are deleted.

    Returns:
        A plan whose entries are ordered the way apply walks them.
    """
    entries: list[PlanEntry] = []

    entries += _simple_diff(
        EntityKind.CUSTOM_FIELD,
        current.custom_fields,
        incoming.custom_fields,
        _CUSTOM_FIELD_FIELDS,
        "name",
        prune=prune,
        natural_key="name",
    )
    entries += _simple_diff(
        EntityKind.LINK,
        current.links,
        incoming.links,
        _LINK_FIELDS,
        "name",
        prune=prune,
    )
    entries += _simple_diff(
        EntityKind.PAGE,
        current.pages,
        incoming.pages,
        _PAGE_FIELDS,
        "slug",
        prune=prune,
        natural_key="slug",
    )
    entries += _simple_diff(
        EntityKind.FILE,
        current.files,
        incoming.files,
        _FILE_FIELDS,
        "name",
        prune=prune,
    )

    current_challenges = {c.id: c for c in current.challenges}
    current_titles = {c.title: c.id for c in current.challenges}
    current_questions = {q.id: (c, q) for c, q in current.questions()}
    incoming_question_ids = {q.id for _, q in incoming.questions()}

    for challenge in incoming.challenges:
        conflict = _natural_key_conflict(current_titles, challenge, "title")
        if conflict is not None:
            entries.append(
                _entry(
                    EntityKind.CHALLENGE,
                    challenge.id,
                    challenge.title,
                    Action.CONFLICT,
                    reason=conflict,
                )
            )
            continue
        challenge_entry = _challenge_entry(
            current_challenges.get(challenge.id), challenge
        )
        entries.append(challenge_entry)
        context = {} if challenge_entry.action is Action.RECREATE else current_questions
        for question in challenge.questions:
            entries += _question_entries(context, challenge, question, prune=prune)

    incoming_challenge_ids = {c.id for c in incoming.challenges}
    if prune:
        for challenge in current.challenges:
            if challenge.id not in incoming_challenge_ids:
                entries.append(
                    _entry(
                        EntityKind.CHALLENGE,
                        challenge.id,
                        challenge.title,
                        Action.DELETE,
                    )
                )
        for owner, question in current.questions():
            if (
                question.id not in incoming_question_ids
                and owner.id in incoming_challenge_ids
            ):
                entries.append(
                    _entry(
                        EntityKind.QUESTION,
                        question.id,
                        question.label,
                        Action.DELETE,
                        parent_id=owner.id,
                    )
                )

    entries += _config_entries(current.config, incoming.config, prune=prune)
    return Plan(entries=entries, prune=prune)
