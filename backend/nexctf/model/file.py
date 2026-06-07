from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class File(Base):
    __tablename__ = "stored_files"

    name: Mapped[str]
    s3_key: Mapped[str] = mapped_column(unique=True)
    original_filename: Mapped[str]
    mime_type: Mapped[str | None]
    file_size: Mapped[int | None]
    is_public: Mapped[bool] = mapped_column(default=False)
