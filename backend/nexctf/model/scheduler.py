"""SQLAlchemy models for scheduler_jobs and scheduler_tasks."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class SchedulerJob(Base):
    """A scheduled job."""

    __tablename__ = "scheduler_jobs"

    name: Mapped[str]
    job_type: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    scheduled_at: Mapped[datetime]
    cron_expression: Mapped[str | None] = mapped_column(String(length=128))

    last_run: Mapped[datetime | None]

    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    tasks: Mapped[list[SchedulerTask]] = relationship(
        "SchedulerTask", back_populates="job", cascade="all, delete-orphan"
    )


class SchedulerTask(Base):
    """A single execution record for a SchedulerJob."""

    __tablename__ = "scheduler_tasks"
    __table_args__ = (Index("ix_scheduler_tasks_job_created", "job_id", "created_at"),)

    status: Mapped[str]  # 'pending', 'success', 'failed'
    started_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    error: Mapped[str | None]

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("scheduler_jobs.id", ondelete="CASCADE")
    )
    job: Mapped[SchedulerJob] = relationship("SchedulerJob", back_populates="tasks")
