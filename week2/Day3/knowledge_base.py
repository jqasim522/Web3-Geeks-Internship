"""
knowledge_base.py
A tiny local "document store" the retriever_node pulls from. Deliberately
simple (a Python list of dicts) so the notebook has zero external
dependencies for retrieval and stays fully reproducible offline.
"""

from typing import List, Dict

_DOCS: List[Dict[str, str]] = [
    {
        "id": "doc1",
        "title": "RAG Overview",
        "content": (
            "Retrieval-Augmented Generation (RAG) combines a retriever that "
            "fetches relevant documents from an external knowledge source with "
            "a generator (an LLM) that conditions its answer on those "
            "documents, rather than relying only on parameters learned during "
            "training."
        ),
    },
    {
        "id": "doc2",
        "title": "RAG Reduces Hallucination",
        "content": (
            "Because the model is grounded in retrieved, verifiable text at "
            "generation time, RAG systems produce fewer unsupported or "
            "fabricated claims than a model answering from parametric memory "
            "alone, and answers can cite the specific source passages used."
        ),
    },
    {
        "id": "doc3",
        "title": "RAG Enables Up-to-date Knowledge",
        "content": (
            "RAG lets a system incorporate information newer than the model's "
            "training cutoff, or private/proprietary data, simply by updating "
            "the document index -- no retraining or fine-tuning of the "
            "underlying LLM is required."
        ),
    },
    {
        "id": "doc4",
        "title": "RAG Cost and Efficiency Benefits",
        "content": (
            "RAG is often cheaper than fine-tuning a model on new knowledge: "
            "the base LLM stays frozen and shared across use cases, while "
            "domain knowledge lives in an easily updatable, inspectable "
            "document index instead of being baked into model weights."
        ),
    },
    {
        "id": "doc5",
        "title": "RAG Failure Modes",
        "content": (
            "RAG quality depends heavily on retrieval quality: if the "
            "retriever returns irrelevant or low-quality documents, the "
            "generator can still produce a confidently wrong answer, which is "
            "why retrieval evaluation and document curation matter as much as "
            "the generation step itself."
        ),
    },
]


def retrieve(query: str, k: int = 4) -> List[Dict[str, str]]:
    """
    Extremely simple keyword-overlap 'retriever'. Ranks documents by how many
    query words appear in their title+content, breaking ties by doc order.
    Not meant to be a real search engine -- just enough to make the
    retriever_node's behavior deterministic and inspectable offline.
    """
    query_words = {w.strip(".,?!").lower() for w in query.split() if len(w) > 2}

    def score(doc: Dict[str, str]) -> int:
        text = (doc["title"] + " " + doc["content"]).lower()
        return sum(1 for w in query_words if w in text)

    ranked = sorted(_DOCS, key=score, reverse=True)
    top = [d for d in ranked if score(d) > 0] or _DOCS
    return top[:k]
