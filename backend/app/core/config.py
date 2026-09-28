from functools import lru_cache
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Findora"
    environment: str = "development"
    database_url: str = "sqlite:///./findora.db"
    secret_key: str = "development-only-change-me"
    access_token_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    upload_dir: Path = Path("uploads")
    max_upload_bytes: int = 5_242_880
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "findora@localhost"
    smtp_use_tls: bool = True
    oidc_redirect_base: str = "http://localhost:8080"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @model_validator(mode="after")
    def validate_deployment(self):
        if self.environment == "production":
            if len(self.secret_key) < 32 or "development" in self.secret_key or "change" in self.secret_key: raise ValueError("Production SECRET_KEY must be a strong external secret")
            if "*" in self.cors_list: raise ValueError("Wildcard CORS is not permitted in production")
            if self.database_url.startswith("sqlite"): raise ValueError("Production requires PostgreSQL")
        if self.smtp_username and not self.smtp_password: raise ValueError("SMTP_PASSWORD is required when SMTP_USERNAME is configured")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
