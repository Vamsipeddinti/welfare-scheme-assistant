from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    database_url: str
    jwt_secret: str = Field(min_length=32)
    jwt_issuer: str = 'welfare-assistant'
    access_minutes: int = Field(default=15, ge=1, le=60)
    refresh_days: int = Field(default=7, ge=1, le=30)
    upload_dir: Path = ROOT / 'runtime/uploads'
    chroma_dir: Path = ROOT / 'runtime/chroma'
    model_dir: Path = ROOT / 'runtime/model'
    static_dir: Path | None = None
    embedding_revision: str = 'bc57282bc374d33e0d6c4de27f12dc1c2a87f37a'
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    cors_origins: str = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000'
    demo_mode: bool = False
    llm_mode: str = 'local'
    llm_api_key: str = ''
    llm_model: str = ''
    auth_rate_limit: int = Field(default=30, ge=1)
    expensive_rate_limit: int = Field(default=30, ge=1)

    @field_validator('database_url')
    @classmethod
    def postgres_only(cls, value):
        if value.startswith(('postgres://', 'postgresql://')):
            value = 'postgresql+psycopg://' + value.split('://', 1)[1]
        if not value.startswith('postgresql+psycopg://'):
            raise ValueError('DATABASE_URL must use postgresql+psycopg://; no database fallback is allowed')
        return value

    @field_validator('jwt_secret')
    @classmethod
    def real_secret(cls, value):
        if value.lower().startswith(('change', 'your-', 'example', 'dev-secret')):
            raise ValueError('Generate a random JWT_SECRET using scripts/setup_env.py')
        return value

    @field_validator('llm_mode')
    @classmethod
    def valid_mode(cls, value):
        if value not in {'local', 'live'}:
            raise ValueError('LLM_MODE must be local or live')
        return value


@lru_cache
def settings():
    return Settings()
