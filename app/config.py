"""Application settings, loaded from environment variables or .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view of backend/.env.

    Field names match the variable names in .env.example, lowercased.
    Unknown variables are ignored so the file can grow freely.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pinecone_api_key: str
    pinecone_index: str = "phlaw"
    groq_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    router_model: str = "openai/gpt-oss-20b"
    llm_reasoning_effort: str = "medium"
    router_reasoning_effort: str = "low"
    ingest_token: str = ""
    allowed_origins: str = "http://localhost:3000"
    daily_request_cap: int = 300


@lru_cache
def get_settings():
    """Return the shared Settings instance, creating it on first use.

    Loading is lazy so that modules can be imported (and tests run)
    without a populated .env file.
    """
    return Settings()
