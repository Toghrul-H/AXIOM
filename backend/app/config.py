from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, EmailStr, TypeAdapter, field_validator
from urllib.parse import urlsplit
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "dmi_platform"
    database_user: str = "dmi_app"
    database_password: SecretStr = SecretStr("")
    auth_cookie_secure: bool = False
    smtp_host: str = ''
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ''
    smtp_password: SecretStr = SecretStr('')
    smtp_use_tls: bool = True
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=60)
    email_from_address: str = ''
    email_from_name: str = 'AXIOM'
    frontend_base_url: str = ''

    @field_validator('email_from_address')
    @classmethod
    def validate_sender(cls, value):
        return str(TypeAdapter(EmailStr).validate_python(value)) if value else value

    @field_validator('email_from_name', 'smtp_host', 'smtp_username')
    @classmethod
    def no_header_newlines(cls, value):
        if '\r' in value or '\n' in value:
            raise ValueError('Newlines are not allowed')
        return value

    @field_validator('frontend_base_url')
    @classmethod
    def validate_frontend_url(cls, value):
        if not value:
            return value
        url = urlsplit(value)
        if (not url.hostname or url.username or url.password or url.query or url.fragment
            or url.path not in {'', '/'} or url.scheme not in {'http', 'https'}
            or (url.scheme == 'http' and url.hostname not in {'localhost', '127.0.0.1', '::1'})):
            raise ValueError('Use an HTTPS frontend origin, or local HTTP origin')
        return value.rstrip('/')
    auth_session_hours: int = Field(default=12, ge=1, le=168)
    auth_requests_per_minute: int = Field(default=30, ge=1, le=1000)
    auth_allowed_origins: list[str] = [
        "http://127.0.0.1:3000", "http://localhost:3000",
        "http://127.0.0.1:8000", "http://localhost:8000",
    ]

    def database_url(self) -> URL:
        password = self.database_password.get_secret_value()
        if not password:
            raise RuntimeError(
                "Set DATABASE_PASSWORD in backend/.env or the process environment."
            )
        return URL.create(
            "postgresql+psycopg",
            username=self.database_user,
            password=password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
