from datetime import datetime

from fastapi_toolsets.schemas import PydanticBase

from nexctf.bundle.diff import PlanEntry


class AdminBundleManifestRead(PydanticBase):
    """What the uploaded archive says about itself."""

    format_version: int
    nexctf_version: str
    exported_at: datetime
    challenge_types: list[str]
    solve_types: list[str]
    plugins: list[str]


class AdminBundlePlanRead(PydanticBase):
    """A reviewable plan, plus the staged key ``apply`` re-derives it from."""

    import_key: str
    prune: bool
    manifest: AdminBundleManifestRead
    counts: dict[str, int]
    entries: list[PlanEntry]


class AdminBundleApply(PydanticBase):
    """Apply every write in a reviewed plan."""

    import_key: str
    prune: bool = False


class AdminBundleApplyResult(PydanticBase):
    """What the apply actually wrote."""

    counts: dict[str, int]
    entries: list[PlanEntry]
