"""Pure serializer for a NexCTF content bundle."""

from nexctf.bundle.archive import read_archive, write_archive
from nexctf.bundle.diff import Action, EntityKind, Plan, PlanEntry, diff
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

__all__ = [
    "FORMAT_VERSION",
    "Action",
    "Bundle",
    "BundleFormatError",
    "ChallengeIR",
    "CustomFieldIR",
    "EntityKind",
    "FileIR",
    "HintIR",
    "LinkIR",
    "ManifestIR",
    "PageIR",
    "Plan",
    "PlanEntry",
    "QuestionIR",
    "RequiresIR",
    "SolutionIR",
    "diff",
    "read_archive",
    "read_tree",
    "write_archive",
    "write_tree",
]
