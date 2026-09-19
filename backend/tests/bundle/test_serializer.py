"""The tree/archive serialization: byte stability, safety and purity."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from nexctf.bundle import (
    Bundle,
    BundleFormatError,
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
    read_archive,
    read_tree,
    write_archive,
    write_tree,
)
from nexctf.bundle.slugs import sanitize_filename, slugify, unique_slugs
from nexctf.bundle.tree import CONFIG_PATH

FILE_ID = UUID("0199a000-0000-7000-8000-00000000000f")


def _id(suffix: int) -> UUID:
    return UUID(f"0199a000-0000-7000-8000-{suffix:012d}")


def sample_bundle() -> Bundle:
    """A bundle exercising every entity kind the format carries."""
    return Bundle(
        manifest=ManifestIR(
            nexctf_version="0.10.1",
            exported_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
            requires=RequiresIR(challenge_types=["standard"], solve_types=["match"]),
        ),
        config={"ctf.name": "Test", "ctf.start_time": "2026-01-01T00:00:00+00:00"},
        challenges=[
            ChallengeIR(
                id=_id(1),
                challenge_type="standard",
                title="Héllo Wörld!",
                description="line one\n\nline two",
                writeup=None,
                is_active=True,
                category="web",
                tags=["b", "a"],
                author_username="admin",
                questions=[
                    QuestionIR(
                        id=_id(2),
                        label="Part 1",
                        description="answer it",
                        points=50,
                        file_ids=[FILE_ID],
                        hints=[
                            HintIR(id=_id(4), title="H", content="multi\nline hint")
                        ],
                        solutions=[
                            SolutionIR(
                                id=_id(5),
                                solve_type="match",
                                data={"value": "flag{x}", "case_sensitive": False},
                            )
                        ],
                    )
                ],
            )
        ],
        files=[
            FileIR(
                id=FILE_ID,
                name="attachment",
                original_filename="notes.txt",
                mime_type="text/plain",
                file_size=4,
                sha256="ab",
            )
        ],
        pages=[PageIR(id=_id(6), slug="home", title="Home", content="# Hi\n\nbody")],
        links=[LinkIR(id=_id(7), name="Discord", url="https://x", visibility="public")],
        custom_fields=[
            CustomFieldIR(
                id=_id(8),
                name="school",
                label="School",
                field_type="string",
                target="user",
            )
        ],
    )


def test_tree_round_trip_is_byte_identical() -> None:
    """The phase-1 acceptance criterion: export -> import -> export changes nothing."""
    bundle = sample_bundle()
    blobs = {FILE_ID: b"data"}
    first = write_tree(bundle, blobs)
    reread, reread_blobs = read_tree(first)
    assert write_tree(reread, reread_blobs) == first


def test_archive_round_trip_is_byte_identical() -> None:
    archive = write_archive(write_tree(sample_bundle(), {FILE_ID: b"data"}))
    bundle, blobs = read_tree(read_archive(archive))
    assert write_archive(write_tree(bundle, blobs)) == archive


def test_long_text_lands_in_markdown_siblings() -> None:
    tree = write_tree(sample_bundle())
    assert tree["challenges/hello-world/description.md"] == b"line one\n\nline two\n"
    assert b"line one" not in tree["challenges/hello-world/challenge.yaml"]


def test_no_volatile_field_travels_beside_an_entity() -> None:
    tree = write_tree(sample_bundle())
    for path, raw in tree.items():
        if path == "nexctf.yaml":
            continue
        assert b"exported_at" not in raw
        assert b"created_at" not in raw
        assert b"updated_at" not in raw
        assert b"s3_key" not in raw


def test_a_renamed_challenge_keeps_its_id() -> None:
    """Directory names are navigation; identity is the id inside the file."""
    bundle = sample_bundle()
    bundle.challenges[0].title = "Renamed"
    tree = write_tree(bundle)
    reread, _ = read_tree(tree)
    assert "challenges/renamed/challenge.yaml" in tree
    assert reread.challenges[0].id == _id(1)


def test_colliding_titles_get_distinct_directories() -> None:
    bundle = sample_bundle()
    twin = bundle.challenges[0].model_copy(deep=True)
    twin.id = _id(9)
    twin.questions = []
    bundle.challenges.append(twin)
    tree = write_tree(bundle)
    challenge_dirs = {p.split("/")[1] for p in tree if p.startswith("challenges/")}
    assert len(challenge_dirs) == 2


@pytest.mark.parametrize(
    "name", ["../../etc/passwd", "/abs/path", "a/../../b", "C:/windows/x"]
)
def test_archive_refuses_a_traversing_member(name: str) -> None:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, b"x")
    with pytest.raises(BundleFormatError):
        read_archive(buffer.getvalue())


def _rezip(tree: dict[str, bytes], *, wrapper: str, noise: bool = False) -> bytes:
    """Zip a tree the way a desktop tool does when the folder is zipped back up."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if noise:
            archive.writestr(f"{wrapper}__MACOSX/._nexctf.yaml", b"junk")
            archive.writestr(f"{wrapper}.DS_Store", b"junk")
        for path, raw in tree.items():
            archive.writestr(f"{wrapper}{path}", raw)
    return buffer.getvalue()


@pytest.mark.parametrize("wrapper", ["nexctf-bundle-20260919T120000Z/", "a/b/", ""])
def test_an_edited_bundle_rezipped_as_a_folder_still_reads(wrapper: str) -> None:
    """Unzip, edit, zip the folder: every desktop tool adds its name on top."""
    tree = write_tree(sample_bundle(), {FILE_ID: b"data"})

    reread, _ = read_tree(read_archive(_rezip(tree, wrapper=wrapper, noise=True)))

    assert reread.challenges[0].title == "Héllo Wörld!"


def test_desktop_zip_noise_is_not_part_of_the_tree() -> None:
    tree = write_tree(sample_bundle())
    read_back = read_archive(_rezip(tree, wrapper="bundle/", noise=True))

    assert not any(".DS_Store" in path or "__MACOSX" in path for path in read_back)


def test_archive_refuses_a_non_zip() -> None:
    with pytest.raises(BundleFormatError):
        read_archive(b"not a zip at all")


def test_reading_a_tree_without_a_manifest_fails() -> None:
    with pytest.raises(BundleFormatError):
        read_tree({"links.yaml": b"links: []\n"})


def test_a_user_supplied_filename_cannot_escape_the_tree() -> None:
    bundle = sample_bundle()
    bundle.files[0].original_filename = "../../evil.sh"
    tree = write_tree(bundle, {FILE_ID: b"x"})
    assert f"files/{FILE_ID}/evil.sh" in tree
    assert not any(".." in path for path in tree)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("Héllo Wörld!", "hello-world"), ("   ", "item"), ("a--b", "a-b")],
)
def test_slugify(value: str, expected: str) -> None:
    assert slugify(value) == expected


def test_unique_slugs_do_not_depend_on_input_order() -> None:
    items = [(_id(1), "Same"), (_id(2), "Same")]
    assert unique_slugs(items) == unique_slugs(list(reversed(items)))


@pytest.mark.parametrize(
    ("value", "expected"),
    [("a/b.txt", "b.txt"), ("..", "blob"), ("x?<>.txt", "x.txt")],
)
def test_sanitize_filename(value: str, expected: str) -> None:
    assert sanitize_filename(value) == expected


def test_every_config_value_is_quoted_the_same_way() -> None:
    """Config values are all strings, so the file should not look half-typed."""
    bundle = sample_bundle()
    bundle.config = {
        "ctf.name": "Test",
        "ctf.team_size": "4",
        "canary.enabled": "false",
        "ctf.description": "",
    }
    lines = write_tree(bundle)[CONFIG_PATH].decode("utf-8").splitlines()[1:]

    assert lines == [
        "  canary.enabled: 'false'",
        "  ctf.description: ''",
        "  ctf.name: 'Test'",
        "  ctf.team_size: '4'",
    ]


def test_a_multi_line_config_value_stays_a_block_scalar() -> None:
    """Quoting must not fold a newline, which would not round-trip."""
    bundle = sample_bundle()
    bundle.config = {"appearance.custom_css": "body {\n  color: red;\n}"}

    tree = write_tree(bundle)

    assert b"|-" in tree[CONFIG_PATH]
    assert read_tree(tree)[0].config == bundle.config


def test_the_serializer_never_imports_the_database_layer() -> None:
    """The authoring CLI reuses this package without a database."""
    import subprocess
    import sys

    source = (
        "import sys, nexctf.bundle;"
        "banned = {'sqlalchemy', 'aioboto3', 'fastapi'} & set(sys.modules);"
        "print(sorted(banned))"
    )
    result = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
