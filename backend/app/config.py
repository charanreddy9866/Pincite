"""Runtime configuration from environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value in (None, "") else value.lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        openai_key = os.getenv("OPENAI_API_KEY") or None
        gemini_key = os.getenv("GEMINI_API_KEY") or None

        # Provider: OpenAI if its key is set, otherwise Google Gemini (free tier), otherwise none.
        # Both are called through the OpenAI SDK; Gemini via its OpenAI-compatible endpoint.
        if openai_key:
            self.provider = "openai"
            self.api_key: str | None = openai_key
            self.base_url: str | None = os.getenv("OPENAI_BASE_URL") or None
            self.chat_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self.embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            self.embeddings_enabled: bool = _flag("EMBEDDINGS", True)
        elif gemini_key:
            self.provider = "gemini"
            self.api_key = gemini_key
            self.base_url = GEMINI_BASE_URL
            # Flash-Lite has the largest free daily quota; override with GEMINI_MODEL.
            self.chat_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
            self.embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
            # Off by default to save free-tier quota; keyword search alone passes the retrieval eval.
            self.embeddings_enabled = _flag("EMBEDDINGS", False)
        else:
            self.provider = None
            self.api_key = None
            self.base_url = None
            self.chat_model = ""
            self.embedding_model = ""
            self.embeddings_enabled = False

        self.database_path: Path = Path(os.getenv("DATABASE_PATH", "data/pincite.db"))
        # When set, every /api request must send this value in the X-Access-Code header.
        self.access_code: str | None = os.getenv("ACCESS_CODE") or None
        self.allowed_origins: list[str] = [
            o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()
        ]
        self.max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "25"))
        self.ocr_enabled: bool = _flag("OCR_ENABLED", True)
        self.static_dir: Path = Path(os.getenv("STATIC_DIR", "static"))
        self.chunk_size: int = 900
        self.chunk_overlap: int = 150
        self.top_k: int = 6
        self.max_agent_steps: int = 4

    @property
    def llm_enabled(self) -> bool:
        return bool(self.api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
