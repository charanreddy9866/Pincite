"""Runtime configuration from environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
        self.chat_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.database_path: Path = Path(os.getenv("DATABASE_PATH", "data/pincite.db"))
        # When set, every /api request must send this value in the X-Access-Code header.
        self.access_code: str | None = os.getenv("ACCESS_CODE") or None
        self.allowed_origins: list[str] = [
            o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()
        ]
        self.max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "25"))
        self.ocr_enabled: bool = os.getenv("OCR_ENABLED", "true").lower() == "true"
        self.static_dir: Path = Path(os.getenv("STATIC_DIR", "static"))
        self.chunk_size: int = 900
        self.chunk_overlap: int = 150
        self.top_k: int = 6
        self.max_agent_steps: int = 4

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
