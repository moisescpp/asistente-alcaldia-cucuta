from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Asistente de Tramites Estrella - Alcaldia de Cucuta"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    frontend_url: str = "http://localhost:5173"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    response_model: str = "gpt-5-nano"
    response_max_output_tokens: int = 450
    response_reasoning_effort: str = "minimal"
    response_text_verbosity: str = "low"
    admin_access_pin: str = "246810"
    admin_session_secret: str = "cucuta-admin-session-secret"
    admin_session_ttl_hours: int = 10
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


settings = Settings()
