from datetime import datetime

from sqlalchemy import JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Enrollment(Base):
    __tablename__ = "learning_enrollments"
    user_id: Mapped[str] = mapped_column(primary_key=True)
    context: Mapped[str]
    release_id: Mapped[str]
    watched_seconds: Mapped[float] = mapped_column(default=0)
    playback_id: Mapped[str | None]
    position_seconds: Mapped[float] = mapped_column(default=0)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    playground: Mapped[dict | None] = mapped_column(JSON)
    interview: Mapped[dict | None] = mapped_column(JSON)


class ManualCompletion(Base):
    __tablename__ = "learning_completions"
    user_id: Mapped[str] = mapped_column(primary_key=True)
    context: Mapped[str] = mapped_column(primary_key=True)
    stage: Mapped[str] = mapped_column(primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
