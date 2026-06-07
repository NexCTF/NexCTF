"""SQLAlchemy models for scheduler_jobs and scheduler_tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from nexctf.model.user import User


class SchedulerJob(Base):
    """A scheduled one-shot job.

    Fires once at `scheduled_at` (UTC). After execution `is_active` is set to
    False so the job does not re-fire.
    """

    __tablename__ = "scheduler_jobs"

    name: Mapped[str]
    job_type: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    scheduled_at: Mapped[Any] = mapped_column(DateTime(timezone=True))
    cron_expression: Mapped[str | None] = mapped_column(
        String(length=128), nullable=True
    )

    last_run: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[User] = relationship("User")

    tasks: Mapped[list[SchedulerTask]] = relationship(
        "SchedulerTask", back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def created_by_username(self) -> str | None:
        return self.created_by.username if self.created_by else None

    def __repr__(self) -> str:
        return f"<SchedulerJob id={self.id} name={self.name!r} type={self.job_type!r}>"


class SchedulerTask(Base):
    """A single execution record for a SchedulerJob."""

    __tablename__ = "scheduler_tasks"

    status: Mapped[str]  # 'pending', 'success', 'failed'
    started_at: Mapped[Any] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None]

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("scheduler_jobs.id", ondelete="CASCADE")
    )
    job: Mapped[SchedulerJob] = relationship("SchedulerJob", back_populates="tasks")

    def __repr__(self) -> str:
        return (
            f"<SchedulerTask id={self.id} job_id={self.job_id} status={self.status!r}>"
        )
