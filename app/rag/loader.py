from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from .config import settings


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_properties() -> list[dict[str, Any]]:
    return load_json(settings.properties_json)


def load_faqs() -> list[dict[str, Any]]:
    return load_jsonl(settings.faqs_jsonl)


def load_developers() -> list[dict[str, Any]]:
    payload = load_json(settings.developers_json)
    return payload.get("developers", [])


def build_documents() -> list[Document]:
    docs: list[Document] = []

    for row in load_properties():
        content = (
            f"Property {row['property_id']} in {row['city']} {row['area']}. "
            f"Type {row['property_type']}, purpose {row['purpose']}, "
            f"price {row['price_formatted']} ({row['price_pkr']} PKR), "
            f"size {row['size_sqft']} sqft, beds {row.get('bedrooms')}, "
            f"installment {'yes' if row.get('has_installment_plan') else 'no'}. "
            f"Description: {row['description']}"
        )
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "source": "properties",
                    "property_id": row["property_id"],
                    "city": row["city"],
                    "area": row["area"],
                    "purpose": row["purpose"],
                    "property_type": row["property_type"],
                },
            )
        )

    for faq in load_faqs():
        docs.append(
            Document(
                page_content=f"Q: {faq['question']}\nA: {faq['answer']}",
                metadata={"source": "faqs", "faq_id": faq["faq_id"], "category": faq["category"]},
            )
        )

    for dev in load_developers():
        docs.append(
            Document(
                page_content=(
                    f"Developer {dev['developer']}. Reputation: {dev['reputation_notes']}. "
                    f"Risk note: {dev['risk_note']}. Projects: {', '.join(dev.get('top_projects', []))}"
                ),
                metadata={"source": "developers", "developer": dev["developer"]},
            )
        )

    return docs
