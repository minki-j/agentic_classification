from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator

# from dotenv import load_dotenv

# # Load .env file explicitly before settings initialization
# load_dotenv(override=True)


class Settings(BaseSettings):
    LOG_LEVEL: str = ""

    # Project info
    PROJECT_NAME: str = "Self-Evolving Taxonomy Agent API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = "your-secret-key-here"  # Change this in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 360  # 6 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "taxonomy_agent"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = []
    FRONTEND_URL: str = "http://localhost:3000"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # WebSocket
    WS_MESSAGE_QUEUE_SIZE: int = 100

    # Classification settings
    DEFAULT_BATCH_SIZE: int = 10
    DEFAULT_INITIAL_BATCH_SIZE: int = 50
    DEFAULT_MAJORITY_THRESHOLD: float = 0.5
    DEFAULT_TOTAL_INVOCATIONS: int = 20
    DEFAULT_MODELS: List[str] = ["gpt-4o-mini", "gpt-4o"]

    # LangSmith Tracing
    LANGSMITH_TRACING: Optional[str] = None
    LANGSMITH_ENDPOINT: Optional[str] = None
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: Optional[str] = None

    # LLM API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # LangGraph Configuration
    LANGGRAPH_STUDIO: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
