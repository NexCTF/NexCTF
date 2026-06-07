from fastapi_toolsets.schemas import PydanticBase


class AdminPluginRead(PydanticBase):
    key: str
    name: str
    display_name: str
    version: str | None
    description: str | None
    authors: list[str]
    repo_url: str | None
    homepage_url: str | None
    is_builtin: bool
    is_active: bool
    is_official: bool
    load_error: str | None = None


class PluginManifestEntry(PydanticBase):
    key: str
    remote_entry: str
    slots: list[str]
    challenge_types: list[str] | None
