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
    is_disabled: bool
    has_config: bool
    missing_bundles: list[str]
    load_error: str | None = None


class PluginStylesheet(PydanticBase):
    url: str
    integrity: str


class PluginPage(PydanticBase):
    path: str
    label: str | dict[str, str]
    icon: str | None
    section: str


class PluginManifestEntry(PydanticBase):
    key: str
    remote_entry: str
    integrity: str
    stylesheet: PluginStylesheet | None
    slots: list[str]
    pages: list[PluginPage]
    challenge_types: list[str] | None
