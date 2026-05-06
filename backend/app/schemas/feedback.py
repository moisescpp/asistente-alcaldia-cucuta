from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


ScaleValue = Annotated[int, Field(ge=1, le=5)]


class CitizenFeedbackCreate(BaseModel):
    participant_name: str | None = Field(default=None, max_length=120)
    participant_profile: str | None = Field(default=None, max_length=120)
    tested_question: str | None = None
    found_answer: bool | None = None
    clarity_rating: ScaleValue
    speed_rating: ScaleValue
    visual_rating: ScaleValue
    sus_1: ScaleValue
    sus_2: ScaleValue
    sus_3: ScaleValue
    sus_4: ScaleValue
    sus_5: ScaleValue
    sus_6: ScaleValue
    sus_7: ScaleValue
    sus_8: ScaleValue
    sus_9: ScaleValue
    sus_10: ScaleValue
    confusion_notes: str | None = None
    suggestions: str | None = None

    @field_validator(
        "participant_name",
        "participant_profile",
        "tested_question",
        "confusion_notes",
        "suggestions",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class CitizenFeedbackRead(CitizenFeedbackCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sus_score: float
    created_at: datetime
