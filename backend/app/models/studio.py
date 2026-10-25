from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class StudioCourseContent(Base):
    __tablename__ = "studio_course_content"
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    version: Mapped[int] = mapped_column(default=1)
    script_text: Mapped[str] = mapped_column(Text, default="")
    script_filename: Mapped[str] = mapped_column(default="")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StudioEvaluation(Base):
    __tablename__ = "studio_evaluations"
    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    revision: Mapped[int]
    content_hash: Mapped[str]
    passed: Mapped[bool]
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    evaluated_by: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StudioAuthorization(Base):
    __tablename__ = "studio_authorizations"
    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    evaluation_id: Mapped[str] = mapped_column(ForeignKey("studio_evaluations.id"))
    revision: Mapped[int]
    content_hash: Mapped[str]
    expert_id: Mapped[str]
    authorized_by: Mapped[str]
    note: Mapped[str]
    release_id: Mapped[str | None] = mapped_column(ForeignKey("releases.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StudioAudit(Base):
    __tablename__ = "studio_audit"
    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    action: Mapped[str]
    actor_id: Mapped[str]
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
