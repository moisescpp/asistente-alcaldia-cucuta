from pydantic import BaseModel, field_validator


class AdminSessionRequest(BaseModel):
    pin: str

    @field_validator("pin", mode="before")
    @classmethod
    def clean_pin(cls, value: str | None) -> str:
        return "" if value is None else str(value).strip()


class AdminSessionRead(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in_seconds: int


class AdminSessionStatus(BaseModel):
    authenticated: bool
