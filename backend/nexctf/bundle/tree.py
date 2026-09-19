"""The git-storable tree serialization: ``Bundle`` <-> ``{path: bytes}``."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ValidationError

from nexctf.bundle.errors import BundleFormatError
from nexctf.bundle.ir import (
    Bundle,
    ChallengeIR,
    CustomFieldIR,
    FileIR,
    LinkIR,
    ManifestIR,
    PageIR,
    QuestionIR,
    SolutionIR,
)
from nexctf.bundle.slugs import sanitize_filename, slugify, unique_slugs
from nexctf.bundle.yamlio import (
    ConfigValue,
    dump_markdown,
    dump_yaml,
    load_markdown,
    load_yaml,
    ordered,
)

MANIFEST_PATH = "nexctf.yaml"
CONFIG_PATH = "config.yaml"
LINKS_PATH = "links.yaml"
CUSTOM_FIELDS_PATH = "custom-fields.yaml"
GITATTRIBUTES_PATH = ".gitattributes"
CHALLENGES_DIR = "challenges"
FILES_DIR = "files"
PAGES_DIR = "pages"

GITATTRIBUTES = "files/** filter=lfs diff=lfs merge=lfs -text\n"

_FRONTMATTER = "---"

_CHALLENGE_KEYS = [
    "id",
    "challenge_type",
    "title",
    "category",
    "tags",
    "is_active",
    "sequential",
    "author",
    "data",
]
_QUESTION_KEYS = [
    "id",
    "label",
    "index",
    "points",
    "malus",
    "input_type",
    "trap_flags",
    "tags",
    "files",
    "hints",
    "solutions",
]
_HINT_KEYS = ["id", "title", "cost", "order", "content"]
_SOLUTION_KEYS = ["id", "solve_type", "data"]
_FILE_KEYS = [
    "id",
    "name",
    "original_filename",
    "mime_type",
    "file_size",
    "is_public",
    "sha256",
]
_PAGE_KEYS = ["id", "slug", "title", "is_published", "nav_placement"]
_LINK_KEYS = ["id", "name", "url", "visibility", "is_enabled"]
_CUSTOM_FIELD_KEYS = [
    "id",
    "name",
    "label",
    "field_type",
    "target",
    "is_required",
    "is_public",
    "is_self_editable",
    "show_in_scoreboard",
]


def _dump(node: Any, keys: list[str]) -> dict[str, Any]:
    """Project an IR node onto its fixed key order, as JSON primitives."""
    return ordered(node.model_dump(mode="json"), keys)


def _paths(tree: dict[str, bytes], prefix: str, suffix: str) -> list[str]:
    """Tree paths under *prefix* ending in *suffix*, in read order."""
    return sorted(p for p in tree if p.startswith(prefix) and p.endswith(suffix))


def _solution_yaml(solution: SolutionIR) -> dict[str, Any]:
    data = _dump(solution, _SOLUTION_KEYS)
    if not data.get("data"):
        data.pop("data", None)
    return data


def _question_yaml(question: QuestionIR) -> dict[str, Any]:
    raw = question.model_dump(mode="json")
    raw["files"] = sorted(str(f) for f in question.file_ids)
    raw["tags"] = sorted(question.tags)
    raw["hints"] = [
        _dump(h, _HINT_KEYS)
        for h in sorted(question.hints, key=lambda h: (h.order, str(h.id)))
    ]
    raw["solutions"] = [
        _solution_yaml(s)
        for s in sorted(question.solutions, key=lambda s: (s.solve_type, str(s.id)))
    ]
    return ordered(raw, _QUESTION_KEYS)


def _challenge_yaml(challenge: ChallengeIR) -> dict[str, Any]:
    raw = challenge.model_dump(mode="json")
    raw["tags"] = sorted(challenge.tags)
    raw["author"] = challenge.author_username
    body = ordered(raw, _CHALLENGE_KEYS)
    if challenge.author_username is None:
        body.pop("author", None)
    if not challenge.data:
        body.pop("data", None)
    return body


def _page_bytes(page: PageIR) -> bytes:
    """A page as YAML frontmatter followed by its markdown body."""
    front = dump_yaml(_dump(page, _PAGE_KEYS)).decode("utf-8")
    return f"{_FRONTMATTER}\n{front}{_FRONTMATTER}\n".encode() + dump_markdown(
        page.content
    )


def write_tree(
    bundle: Bundle, blobs: dict[UUID, bytes] | None = None
) -> dict[str, bytes]:
    """Serialize a bundle (and optionally its file blobs) to a path -> bytes tree."""
    blobs = blobs or {}
    tree: dict[str, bytes] = {
        MANIFEST_PATH: dump_yaml(
            ordered(
                bundle.manifest.model_dump(mode="json"),
                ["format_version", "nexctf_version", "exported_at", "requires"],
            )
        ),
        CONFIG_PATH: dump_yaml(
            {
                "config": {
                    k: ConfigValue(bundle.config[k]) for k in sorted(bundle.config)
                }
            }
        ),
        GITATTRIBUTES_PATH: GITATTRIBUTES.encode("utf-8"),
        LINKS_PATH: dump_yaml(
            {
                "links": [
                    _dump(link, _LINK_KEYS)
                    for link in sorted(bundle.links, key=lambda x: str(x.id))
                ]
            }
        ),
        CUSTOM_FIELDS_PATH: dump_yaml(
            {
                "custom_fields": [
                    _dump(field, _CUSTOM_FIELD_KEYS)
                    for field in sorted(bundle.custom_fields, key=lambda x: x.name)
                ]
            }
        ),
    }

    challenges = sorted(bundle.challenges, key=lambda c: str(c.id))
    slugs = unique_slugs([(c.id, c.title) for c in challenges])
    for challenge in challenges:
        base = f"{CHALLENGES_DIR}/{slugs[challenge.id]}"
        tree[f"{base}/challenge.yaml"] = dump_yaml(_challenge_yaml(challenge))
        if challenge.description is not None:
            tree[f"{base}/description.md"] = dump_markdown(challenge.description)
        if challenge.writeup is not None:
            tree[f"{base}/writeup.md"] = dump_markdown(challenge.writeup)
        questions = sorted(challenge.questions, key=lambda q: (q.index, str(q.id)))
        for position, question in enumerate(questions, start=1):
            qdir = f"{base}/questions/{position:02d}-{slugify(question.label)}"
            tree[f"{qdir}/question.yaml"] = dump_yaml(_question_yaml(question))
            if question.description is not None:
                tree[f"{qdir}/description.md"] = dump_markdown(question.description)

    for file in sorted(bundle.files, key=lambda f: str(f.id)):
        tree[f"{FILES_DIR}/{file.id}/meta.yaml"] = dump_yaml(_dump(file, _FILE_KEYS))
        blob = blobs.get(file.id)
        if blob is not None:
            name = sanitize_filename(file.original_filename)
            tree[f"{FILES_DIR}/{file.id}/{name}"] = blob

    for page in sorted(bundle.pages, key=lambda p: p.slug):
        tree[f"{PAGES_DIR}/{page.slug}.md"] = _page_bytes(page)

    return tree


def _require(tree: dict[str, bytes], path: str) -> bytes:
    if path not in tree:
        raise BundleFormatError(f"missing {path}")
    return tree[path]


def _model(cls: Any, data: dict[str, Any], path: str) -> Any:
    try:
        return cls.model_validate(data)
    except ValidationError as exc:
        raise BundleFormatError(f"{path}: {exc}") from exc


def _read_page(path: str, raw: bytes) -> PageIR:
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if not text.startswith(f"{_FRONTMATTER}\n"):
        raise BundleFormatError(f"{path}: missing frontmatter")
    front, _, body = text[len(_FRONTMATTER) + 1 :].partition(f"\n{_FRONTMATTER}\n")
    data = load_yaml(front.encode("utf-8"))
    data["content"] = load_markdown(body.lstrip("\n").encode("utf-8"))
    return _model(PageIR, data, path)


def _read_challenge(tree: dict[str, bytes], base: str) -> ChallengeIR:
    data = load_yaml(tree[f"{base}/challenge.yaml"])
    data["author_username"] = data.pop("author", None)
    for field, filename in (
        ("description", "description.md"),
        ("writeup", "writeup.md"),
    ):
        raw = tree.get(f"{base}/{filename}")
        data[field] = None if raw is None else load_markdown(raw)

    questions: list[QuestionIR] = []
    for path in _paths(tree, f"{base}/questions/", "/question.yaml"):
        qdir = path.rsplit("/", 1)[0]
        qdata = load_yaml(tree[path])
        qdata["file_ids"] = qdata.pop("files", [])
        description = tree.get(f"{qdir}/description.md")
        qdata["description"] = (
            None if description is None else load_markdown(description)
        )
        questions.append(_model(QuestionIR, qdata, path))
    data["questions"] = questions
    return _model(ChallengeIR, data, f"{base}/challenge.yaml")


def read_tree(tree: dict[str, bytes]) -> tuple[Bundle, dict[UUID, bytes]]:
    """Parse a path -> bytes tree back into a bundle and its file blobs."""
    manifest = _model(
        ManifestIR, load_yaml(_require(tree, MANIFEST_PATH)), MANIFEST_PATH
    )

    config_raw = load_yaml(tree.get(CONFIG_PATH, b"")).get("config") or {}
    if not isinstance(config_raw, dict):
        raise BundleFormatError(f"{CONFIG_PATH}: 'config' must be a mapping")
    config = {str(k): str(v) for k, v in config_raw.items()}

    links = [
        _model(LinkIR, item, LINKS_PATH)
        for item in load_yaml(tree.get(LINKS_PATH, b"")).get("links") or []
    ]
    custom_fields = [
        _model(CustomFieldIR, item, CUSTOM_FIELDS_PATH)
        for item in load_yaml(tree.get(CUSTOM_FIELDS_PATH, b"")).get("custom_fields")
        or []
    ]

    challenges = [
        _read_challenge(tree, path.rsplit("/", 1)[0])
        for path in _paths(tree, f"{CHALLENGES_DIR}/", "/challenge.yaml")
    ]

    files: list[FileIR] = []
    blobs: dict[UUID, bytes] = {}
    by_directory: dict[str, list[str]] = {}
    for path in tree:
        if path.startswith(f"{FILES_DIR}/") and path.count("/") > 1:
            directory = "/".join(path.split("/")[:2])
            by_directory.setdefault(directory, []).append(path)
    for path in _paths(tree, f"{FILES_DIR}/", "/meta.yaml"):
        file = _model(FileIR, load_yaml(tree[path]), path)
        files.append(file)
        directory = path.rsplit("/", 1)[0]
        for candidate in sorted(by_directory.get(directory, [])):
            if candidate != path:
                blobs[file.id] = tree[candidate]
                break

    pages = [
        _read_page(path, tree[path]) for path in _paths(tree, f"{PAGES_DIR}/", ".md")
    ]

    return (
        Bundle(
            manifest=manifest,
            config=config,
            challenges=challenges,
            files=files,
            pages=pages,
            links=links,
            custom_fields=custom_fields,
        ),
        blobs,
    )
