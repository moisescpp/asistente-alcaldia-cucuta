from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Asistente de Tramites Estrella - Alcaldia de Cucuta"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    frontend_url: str = "http://localhost:5173"
    frontend_urls: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    response_model: str = "gpt-5-nano"
    response_max_output_tokens: int = 450
    response_reasoning_effort: str = "minimal"
    response_text_verbosity: str = "low"
    admin_access_pin: str = "246810"
    admin_session_secret: str = "cucuta-admin-session-secret"
    admin_session_ttl_minutes: int = 5
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/alcaldia_cucuta"
    )
    embedding_dimensions: int = 1536

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def frontend_origins(self) -> list[str]:
        origins: list[str] = []

        for raw_value in (self.frontend_url, self.frontend_urls):
            for candidate in str(raw_value or "").replace("\n", ",").split(","):
                cleaned = candidate.strip().rstrip("/")
                if cleaned and cleaned not in origins:
                    origins.append(cleaned)

        return origins or ["http://localhost:5173"]

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgresql+psycopg://"):
            return self.database_url
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace(
                "postgres://",
                "postgresql+psycopg://",
                1,
            )

        return self.database_url


settings = Settings()
