from __future__ import annotations

from langchain_chroma import Chroma
from langchain_core.documents import Document

from .config import settings
from .embedder import get_embeddings


COLLECTION_NAME = "realestate_kb"


def upsert_documents(documents: list[Document]) -> Chroma:
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(settings.chroma_dir),
    )
    store.add_documents(documents)
    return store


def load_store() -> Chroma:
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(settings.chroma_dir),
    )
