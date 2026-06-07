from datetime import datetime
from uuid import UUID

from fastapi_toolsets.schemas import PydanticBase


class AdminPageRead(PydanticBase):
    """Full page representation for admin use."""

    id: UUID
    slug: str
    title: str
    content: str
    is_published: bool
    nav_placement: str | None
    created_at: datetime
    updated_at: datetime


class AdminPageCreate(PydanticBase):
    """Fields required to create a new custom page."""

    slug: str
    title: str
    content: str = ""
    is_published: bool = False
    nav_placement: str | None = None


class AdminPageUpdate(PydanticBase):
    """Partial update for a custom page."""

    slug: str | None = None
    title: str | None = None
    content: str | None = None
    is_published: bool | None = None
    nav_placement: str | None = None


class PublicPageRead(PydanticBase):
    """Minimal representation used for navigation lists."""

    slug: str
    title: str
    nav_placement: str | None


class PublicPageDetail(PydanticBase):
    """Full published page content for rendering."""

    slug: str
    title: str
    content: str
    nav_placement: str | None
