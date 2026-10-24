from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, utcnow


class StudioAnalysisRun(Base):
    __tablename__ = "studio_analysis_runs"
    id: Mapped[str] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    revision: Mapped[int]
    source_hash: Mapped[str]
    source_notes: Mapped[str] = mapped_column(Text)
    source_label: Mapped[str]
    mode: Mapped[str]
    model: Mapped[str]
    status: Mapped[str]
    stage: Mapped[str]
    proposals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    evaluation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    requested_by: Mapped[str]
    release_id: Mapped[str | None] = mapped_column(ForeignKey("releases.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
