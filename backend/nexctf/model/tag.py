from sqlalchemy.orm import Mapped

from .base import Base


class Tag(Base):
    __tablename__ = "tag"

    name: Mapped[str]
    description: Mapped[str]
    color: Mapped[str]
