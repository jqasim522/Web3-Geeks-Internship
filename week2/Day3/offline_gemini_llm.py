"""
offline_gemini_llm.py

Reproducibility shim used across this week's LangGraph/LangChain
notebooks. `build_llm()` returns:

  - a real `ChatGoogleGenerativeAI("gemini-2.5-flash")` if the
    `GEMINI_API_KEY` environment variable is set, or
  - a small scripted `OfflineGeminiLLM` that implements the exact same
    `.invoke(prompt) -> AIMessage`-shaped interface (an object with a
    `.content` string attribute), so the notebook runs end-to-end with
    no API key and no network access.

Only the text-generation step is scripted offline -- every graph, node,
edge, conditional route, interrupt, and checkpoint in the notebook still
executes for real. Set `GEMINI_API_KEY` and re-run for live Gemini
reasoning; no other code needs to change.
"""

import os
from dataclasses import dataclass


@dataclass
class AIMessage:
    """Minimal stand-in for langchain_core.messages.AIMessage: just .content."""
    content: str


class OfflineGeminiLLM:
    """
    Deterministic, rule-based scripted 'LLM' used only when no
    GEMINI_API_KEY is available. It pattern-matches on the *shape* of the
    prompts this notebook's nodes send (plan / draft / revise / critique)
    so the self-correction loop and human-in-the-loop demo behave
    consistently and reproducibly across runs.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash (offline stub)"):
        self.model_name = model_name

    def invoke(self, prompt: str) -> AIMessage:
        text = prompt.strip()

        # --- planner_node prompt -------------------------------------
        if text.startswith("Create a short research plan"):
            question = text.split(":", 1)[-1].strip()
            content = (
                f"1. Identify the core claim behind: {question}\n"
                "2. Retrieve supporting evidence from the knowledge base\n"
                "3. Synthesize the evidence into a concise, sourced answer"
            )
            return AIMessage(content=content)

        # --- critique_node prompt --------------------------------------
        if text.startswith("Critique the following draft"):
            attempt = 1
            if "(attempt" in text:
                try:
                    attempt = int(text.split("(attempt", 1)[1].split(")")[0].strip())
                except (ValueError, IndexError):
                    attempt = 1

            if attempt <= 1:
                content = (
                    "Needs revision: the draft lists benefits but doesn't "
                    "tie each claim back to a specific retrieved document, "
                    "and it omits the retrieval-quality caveat from doc5. "
                    "Please cite document ids and add the caveat."
                )
            else:
                content = (
                    "Good - the draft is well-grounded in the retrieved "
                    "documents, cites sources, and fairly notes the "
                    "retrieval-quality caveat. No further revision needed."
                )
            return AIMessage(content=content)

        # --- drafter_node prompt: revision (has a critique embedded) ----
        if text.startswith("Revise the draft based on this critique"):
            content = (
                "Retrieval-Augmented Generation (RAG) offers several key "
                "benefits, each grounded in the retrieved sources below:\n\n"
                "1. Grounded, less hallucinated answers -- by conditioning "
                "generation on retrieved passages rather than parametric "
                "memory alone [doc1][doc2].\n"
                "2. Up-to-date and private knowledge without retraining -- "
                "new information can be added by updating the document "
                "index, not the model weights [doc3].\n"
                "3. Lower cost than fine-tuning -- the base LLM stays "
                "frozen and shared, while domain knowledge lives in an "
                "inspectable, updatable index [doc4].\n\n"
                "Caveat: these benefits depend on retrieval quality -- a "
                "weak retriever can still lead to a confidently wrong "
                "answer, so retrieval evaluation matters as much as "
                "generation quality [doc5]."
            )
            return AIMessage(content=content)

        # --- drafter_node prompt: first draft ---------------------------
        if text.startswith("Write a draft answer"):
            content = (
                "Retrieval-Augmented Generation (RAG) combines a retriever "
                "with a generator so answers are grounded in retrieved "
                "documents. Reported benefits include reduced hallucination, "
                "the ability to use up-to-date or private knowledge without "
                "retraining the model, and lower cost than fine-tuning since "
                "the base model stays frozen."
            )
            return AIMessage(content=content)

        # --- fallback -----------------------------------------------------
        return AIMessage(content=f"[offline stub response to]: {text[:120]}")


def build_llm(model_name: str = "gemini-3.5-flash"):
    """
    Returns a real ChatGoogleGenerativeAI if GEMINI_API_KEY is set in the
    environment, otherwise an OfflineGeminiLLM with an identical
    .invoke(prompt) -> AIMessage interface.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)

    return OfflineGeminiLLM(model_name=model_name)
