from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CitizenFeedback(Base):
    __tablename__ = "citizen_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    participant_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    participant_profile: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tested_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    found_answer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    clarity_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    speed_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    visual_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    sus_1: Mapped[int] = mapped_column(Integer, nullable=False)
    sus_2: Mapped[int] = mapped_column(Integer, nullable=False)
    sus_3: Mapped[int] = mapped_column(Integer, nullable=False)
    sus_4: Mapped[int] = mapped_column(Integer, nullable=False)
    sus_5: Mapped[int] = mapped_column(Integer, nullable=False)
    sus_6: Mapped[int] = mapped_column(Integer, nullable=False)
    sus_7: Mapped[int] = mapped_column(Integer, nullable=False)
    sus_8: Mapped[int] = mapped_column(Integer, nullable=False)
    sus_9: Mapped[int] = mapped_column(Integer, nullable=False)
    sus_10: Mapped[int] = mapped_column(Integer, nullable=False)
    confusion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
