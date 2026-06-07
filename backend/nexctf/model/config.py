from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ConfigEntry(Base):
    """Stores runtime configuration overrides.

    Only keys that differ from code defaults need a row here.
    """

    __tablename__ = "config_entries"

    key: Mapped[str] = mapped_column(unique=True, index=True)
    value: Mapped[str]
