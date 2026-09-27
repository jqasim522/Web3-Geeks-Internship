"""
crew_tools.py

Two small, fully-local CrewAI tools used by this assignment's crew. Both are
plain Python -- no network calls, no API keys -- so the crew is reproducible
offline (the same "small local data source" pattern used in earlier
assignments' knowledge_base.py). A third tool, the real `FileReadTool` from
`crewai_tools`, is used unmodified for the Content Strategist (it already
only reads local files, so it needs no offline substitute).
"""

import re
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Researcher's tool: local competitor dataset
# ---------------------------------------------------------------------------

_COMPETITORS = {
    "hubspot": {
        "name": "HubSpot",
        "pricing": "Starter CRM Suite from $20/seat/month; core CRM tier is free "
        "with limited features.",
        "features": [
            "All-in-one marketing, sales, and service hubs on one data model",
            "Large ecosystem of native integrations and a public app marketplace",
            "Strong free tier used as a lead-in funnel for paid seats",
        ],
        "position": "Positions itself as the easy-to-adopt, all-in-one platform "
        "for scaling SMBs that don't want to stitch together point tools.",
    },
    "salesforce": {
        "name": "Salesforce",
        "pricing": "Sales Cloud starts around $25/user/month (Starter) up to "
        "$500/user/month (Unlimited+); heavy customization work is usually "
        "billed separately through implementation partners.",
        "features": [
            "Deep customization via Apex/Flow and a huge partner ecosystem",
            "AppExchange marketplace with thousands of add-ons",
            "Enterprise-grade permissioning, reporting, and forecasting",
        ],
        "position": "Positions itself as the enterprise standard -- the safe, "
        "highly configurable choice for large, complex sales orgs.",
    },
    "zoho": {
        "name": "Zoho CRM",
        "pricing": "Plans from about $14/user/month (Standard) to $52/user/month "
        "(Ultimate), notably cheaper than HubSpot or Salesforce at "
        "comparable feature tiers.",
        "features": [
            "Bundled into the wider Zoho One suite of 40+ business apps",
            "Built-in AI assistant (Zia) for lead scoring and forecasting",
            "Generous customization for the price point",
        ],
        "position": "Positions itself as the value pick -- most of the features "
        "of the bigger platforms at a fraction of the per-seat cost.",
    },
}


class CompetitorIntelInput(BaseModel):
    query: str = Field(
        ...,
        description=(
            "A competitor name (HubSpot, Salesforce, or Zoho) to look up, "
            "or 'all' to retrieve all three at once."
        ),
    )


class CompetitorIntelTool(BaseTool):
    name: str = "Competitor Intel Lookup"
    description: str = (
        "Look up pricing, key features, and market positioning for a named "
        "CRM competitor (HubSpot, Salesforce, or Zoho). Pass 'all' to "
        "retrieve all three at once."
    )
    args_schema: Type[BaseModel] = CompetitorIntelInput

    def _run(self, query: str) -> str:
        query_norm = query.strip().lower()
        if query_norm in ("all", "*", ""):
            keys = list(_COMPETITORS.keys())
        else:
            keys = [k for k in _COMPETITORS if k in query_norm or query_norm in k]
            if not keys:
                return (
                    f"No local data for '{query}'. Known competitors: "
                    f"{', '.join(c['name'] for c in _COMPETITORS.values())}."
                )

        chunks = []
        for k in keys:
            c = _COMPETITORS[k]
            feature_lines = "\n".join(f"  - {f}" for f in c["features"])
            chunks.append(
                f"### {c['name']}\n"
                f"Pricing: {c['pricing']}\n"
                f"Key Features:\n{feature_lines}\n"
                f"Market Position: {c['position']}"
            )
        return "\n\n".join(chunks)


# ---------------------------------------------------------------------------
# Editor's tool: lightweight local readability / unverifiable-claim checker
# ---------------------------------------------------------------------------

_FLAGGED_PHRASES = [
    "best-in-class",
    "best in class",
    "the best",
    "guaranteed",
    "#1",
    "number one",
    "always",
    "never fails",
    "100%",
    "world's most",
    "unbeatable",
]


class ReadabilityClaimCheckInput(BaseModel):
    text: str = Field(..., description="The draft text to check.")


class ReadabilityClaimCheckTool(BaseTool):
    name: str = "Readability & Claim Check"
    description: str = (
        "Checks a draft's word count and flags unverifiable superlative "
        "claims (e.g. 'best', 'guaranteed', '#1', 'always') that need a "
        "citation or softer wording. Input: the draft text."
    )
    args_schema: Type[BaseModel] = ReadabilityClaimCheckInput

    def _run(self, text: str) -> str:
        word_count = len(text.split())
        lowered = text.lower()
        flagged = sorted(
            {phrase for phrase in _FLAGGED_PHRASES if phrase in lowered}
        )
        avg_sentence_len = word_count / max(1, len(re.split(r"[.!?]+", text)) - 1 or 1)

        report = [f"Word count: {word_count}", f"Approx. avg sentence length: {avg_sentence_len:.1f} words"]
        if flagged:
            report.append(
                "Flagged unverifiable superlatives: " + ", ".join(flagged)
            )
        else:
            report.append("No unverifiable superlatives found.")
        return "\n".join(report)