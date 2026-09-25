from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 4
    min_wait_seconds: float = 0.5
    max_wait_seconds: float = 6.0

GROQ_RETRY_POLICY = RetryPolicy()

@dataclass(frozen=True)
class RAGSettings:
    base_dir: Path = Path(__file__).resolve().parents[2]
    properties_json: Path = base_dir / "data/properties.json"
    faqs_jsonl: Path = base_dir / "data/faqs.jsonl"
    developers_json: Path = base_dir / "data/developers.json"
    chroma_dir: Path = base_dir / "data/chroma"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    groq_model: str = "openai/gpt-oss-120b"
    gemini_model: str = "gemini-1.5-flash"
    default_chunk_size: int = 512
    default_chunk_overlap: int = 64
    default_k: int = 4

    @property
    def groq_api_key(self) -> str:
        return os.getenv("GROQ_API_KEY", "")

    @property
    def gemini_api_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "")

settings = RAGSettings()
