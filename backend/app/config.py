from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-opus-4-8"
    LLM_MAX_TOKENS: int = 8192

    # QueryLens metadata store (connections, conversations, query logs)
    APP_MONGODB_URI: str = "mongodb://localhost:27017"
    APP_DATABASE: str = "querylens"

    # Demo connections registered at startup (bundled datasets)
    DEMO_MONGODB_URI: str = "mongodb://localhost:27017"
    DEMO_DATABASE: str = "demo_ecommerce"
    DEMO_POSTGRES_URI: str = "postgresql://querylens:querylens@localhost:5432"
    DEMO_POSTGRES_DATABASE: str = "demo_hr"

    # Query execution
    MAX_QUERY_RESULTS: int = 0  # 0 = unlimited; positive number enforces a cap
    LLM_PREVIEW_LIMIT: int = 50  # rows shown to the LLM when formatting the answer

    # Schema discovery
    SCHEMA_SAMPLE_SIZE: int = 100  # documents sampled per collection
    SCHEMA_CACHE_TTL: int = 300  # seconds before a discovered schema is re-inferred

    LOG_LEVEL: str = "INFO"

    # Local dev runs from backend/ with .env at the repo root; Docker injects env vars
    model_config = {"env_file": ("../.env", ".env"), "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
