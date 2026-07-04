import enum

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Visibility(enum.Enum):
    PUBLIC = "public"
    ADMIN = "admin"


class Link(Base):
    """Link to external ressources."""

    __tablename__ = "links"

    name: Mapped[str]
    url: Mapped[str]
    visibility: Mapped[Visibility]
    is_enabled: Mapped[bool] = mapped_column(index=True)
