from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class AppMeta(Base):
    __tablename__ = "app_meta"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    equipment: Mapped[str]
    description: Mapped[str | None]
    language: Mapped[str]
    source_label: Mapped[str]
    owner_id: Mapped[str]
    status: Mapped[str]
    active_release_id: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), unique=True)
    revision: Mapped[int]
    status: Mapped[str]
    knowledge_units: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DraftRevision(Base):
    __tablename__ = "draft_revisions"
    __table_args__ = (UniqueConstraint("draft_id", "revision"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"))
    revision: Mapped[int]
    knowledge_units: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    actor_id: Mapped[str]
    reason: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    type: Mapped[str]
    author_id: Mapped[str]
    author_label: Mapped[str]
    content: Mapped[str | None] = mapped_column(Text)
    media_id: Mapped[str | None]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]
    source_label: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    owner_id: Mapped[str]
    original_filename: Mapped[str]
    storage_key: Mapped[str] = mapped_column(unique=True)
    mime_type: Mapped[str]
    container: Mapped[str]
    size_bytes: Mapped[int]
    sha256: Mapped[str]
    duration_ms: Mapped[int]
    video_codec: Mapped[str]
    audio_codec: Mapped[str | None]
    width: Mapped[int]
    height: Mapped[int]
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (UniqueConstraint("task_id", "media_id", "mode", "request_id"),)
    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    media_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"))
    mode: Mapped[str]
    request_id: Mapped[str]
    requested_by: Mapped[str]
    status: Mapped[str]
    stage: Mapped[str]
    attempt_count: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str]
    model_id: Mapped[str]
    prompt_version: Mapped[str]
    input_sha256: Mapped[str]
    provider_file_name: Mapped[str | None]
    provider_file_uri: Mapped[str | None]
    provider_file_state: Mapped[str | None]
    provider_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extraction: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    result_draft_id: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Clarification(Base):
    __tablename__ = "clarifications"
    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"))
    knowledge_unit_id: Mapped[str]
    question: Mapped[str]
    gap_type: Mapped[str]
    priority: Mapped[int]
    status: Mapped[str]
    answer: Mapped[str | None] = mapped_column(Text)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"))
    answered_by: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Release(Base):
    __tablename__ = "releases"
    __table_args__ = (
        UniqueConstraint("task_id", "version"),
        UniqueConstraint("task_id", "source_draft_revision"),
    )
    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    version: Mapped[int]
    source_draft_revision: Mapped[int]
    content_hash: Mapped[str]
    approved_by: Mapped[str]
    approval_note: Mapped[str]
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    task_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    knowledge_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    evidence_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
