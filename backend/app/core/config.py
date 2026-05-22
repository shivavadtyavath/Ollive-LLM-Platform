"""
Central configuration — reads from environment variables with sensible defaults.
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Ollive LLM Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://ollive:ollive@db:5432/ollive"
    DATABASE_SYNC_URL: str = "postgresql://ollive:ollive@db:5432/ollive"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # LLM Providers (all free / open-source friendly)
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    GROQ_API_KEY: str = ""          # groq.com — free tier, very fast
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    OLLAMA_BASE_URL: str = "http://ollama:11434"   # local open-source models

    OPENROUTER_API_KEY: str = ""    # openrouter.ai — free models available
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Default provider / model
    DEFAULT_PROVIDER: str = "groq"
    DEFAULT_MODEL: str = "llama-3.1-8b-instant"

    # Ingestion
    INGESTION_BATCH_SIZE: int = 50
    INGESTION_FLUSH_INTERVAL: int = 5   # seconds

    # PII redaction
    PII_REDACTION_ENABLED: bool = True

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Context window (messages to keep per session)
    MAX_CONTEXT_MESSAGES: int = 20

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
