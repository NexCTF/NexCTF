from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CustomPage(Base):
    __tablename__ = "custom_pages"

    slug: Mapped[str] = mapped_column(unique=True, index=True)
    title: Mapped[str] = mapped_column()
    content: Mapped[str] = mapped_column(default="")
    is_published: Mapped[bool] = mapped_column(default=False)
    nav_placement: Mapped[str | None] = mapped_column(nullable=True)
