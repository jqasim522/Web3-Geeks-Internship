from __future__ import annotations

from collections.abc import Iterable

from langchain_core.documents import Document

from .config import settings
from .store import load_store

SQL_FIRST_KEYWORDS = {
    "price",
    "budget",
    "lakh",
    "crore",
    "bed",
    "bedroom",
    "bath",
    "sqft",
    "available",
    "availability",
    "installment",
    "possession",
    "city",
    "area",
    "dha",
    "bahria",
}


def should_route_sql_first(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in SQL_FIRST_KEYWORDS)


def retrieve_context(query: str, k: int = settings.default_k) -> list[Document]:
    retriever = load_store().as_retriever(search_kwargs={"k": k})
    return retriever.invoke(query)


def format_context(documents: Iterable[Document]) -> str:
    return "\n\n".join(d.page_content for d in documents)
