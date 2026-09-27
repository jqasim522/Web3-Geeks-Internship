from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from .config import GROQ_RETRY_POLICY, settings

PROMPT = (
    "You are a grounded real-estate assistant. Use only provided context and structured facts. "
    "If context is insufficient, say you do not have verified data and offer human callback."
)


class Generator:
    def __init__(self) -> None:
        self.groq = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            temperature=0.2,
        )
        self.gemini = ChatGoogleGenerativeAI(
            google_api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            temperature=0.2,
        )

    @retry(
        stop=stop_after_attempt(GROQ_RETRY_POLICY.attempts),
        wait=wait_exponential_jitter(
            initial=GROQ_RETRY_POLICY.min_wait_seconds,
            max=GROQ_RETRY_POLICY.max_wait_seconds,
        ),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _groq_invoke(self, messages: list[Any]) -> Any:
        return self.groq.invoke(messages)

    def answer(self, user_query: str, context: str) -> str:
        messages = [
            SystemMessage(content=PROMPT),
            HumanMessage(content=f"Context:\n{context}\n\nQuestion:\n{user_query}"),
        ]
        try:
            response = self._groq_invoke(messages)
            return str(response.content)
        except Exception:
            fallback = self.gemini.invoke(messages)
            return str(fallback.content)
