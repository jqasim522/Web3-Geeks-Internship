from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math


WEIGHTS = {
    "budget_fit": 0.35,
    "location_fit": 0.25,
    "spec_fit": 0.20,
    "installment_fit": 0.10,
    "amenities_fit": 0.05,
    "investment_fit": 0.05,
}


@dataclass
class UserPreference:
    budget_max: int
    city: str
    area: str | None = None
    bedrooms_min: int | None = None
    purpose: str = "Sale"
    wants_installment: bool = False
    preferred_amenities: list[str] | None = None
    investment_goal: str | None = None


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def _budget_score(price: int, budget_max: int) -> float:
    if price <= budget_max:
        gap = (budget_max - price) / max(1, budget_max)
        return _bounded(0.7 + (gap * 0.3))
    over = (price - budget_max) / max(1, budget_max)
    return _bounded(1.0 - over)


def score_property(prop: dict[str, Any], pref: UserPreference) -> dict[str, Any]:
    budget_fit = _budget_score(int(prop["price_pkr"]), pref.budget_max)

    city_ok = prop["city"].lower() == pref.city.lower()
    area_ok = True if not pref.area else pref.area.lower() in prop["area"].lower()
    location_fit = 1.0 if (city_ok and area_ok) else 0.4 if city_ok else 0.0

    beds = prop.get("bedrooms")
    spec_fit = 1.0
    if pref.bedrooms_min is not None:
        if beds is None:
            spec_fit = 0.5
        else:
            spec_fit = 1.0 if int(beds) >= pref.bedrooms_min else 0.2

    installment_fit = 1.0 if (not pref.wants_installment or bool(prop.get("has_installment_plan"))) else 0.0

    amenities_fit = 0.5
    wanted = [a.lower() for a in (pref.preferred_amenities or [])]
    if wanted:
        prop_amen = str(prop.get("amenities") or "").lower().split("|")
        hit = len(set(wanted) & set(prop_amen))
        amenities_fit = hit / max(1, len(wanted))

    investment_fit = 0.5
    if pref.investment_goal == "rental_yield":
        investment_fit = 1.0 if prop.get("property_type") in {"Flat", "Studio", "Portion"} else 0.4
    elif pref.investment_goal == "capital_gain":
        investment_fit = 1.0 if "DHA" in prop.get("area", "") or "Bahria" in prop.get("area", "") else 0.5

    components = {
        "budget_fit": budget_fit,
        "location_fit": location_fit,
        "spec_fit": spec_fit,
        "installment_fit": installment_fit,
        "amenities_fit": amenities_fit,
        "investment_fit": investment_fit,
    }
    total = sum(WEIGHTS[k] * components[k] for k in WEIGHTS)

    return {
        "property_id": prop["property_id"],
        "score": round(_bounded(total), 4),
        "components": {k: round(v, 4) for k, v in components.items()},
    }


def rank_properties(properties: list[dict[str, Any]], pref: UserPreference, top_n: int = 5) -> list[dict[str, Any]]:
    eligible = [
        p for p in properties
        if p.get("purpose", "").lower() == pref.purpose.lower() and str(p.get("listing_status", "available")).lower() == "available"
    ]
    scored = [score_property(p, pref) for p in eligible]
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:top_n]


if __name__ == "__main__":
    sample_properties = [
        {
            "property_id": "LAH-0001",
            "price_pkr": 25000000,
            "city": "Lahore",
            "area": "DHA Phase 6",
            "bedrooms": 4,
            "purpose": "Sale",
            "has_installment_plan": False,
            "amenities": "park|brand_new",
            "property_type": "House",
            "listing_status": "available",
        },
        {
            "property_id": "LAH-0002",
            "price_pkr": 22000000,
            "city": "Lahore",
            "area": "Bahria Town",
            "bedrooms": 3,
            "purpose": "Sale",
            "has_installment_plan": True,
            "amenities": "furnished|park",
            "property_type": "Flat",
            "listing_status": "available",
        },
    ]

    pref = UserPreference(
        budget_max=26000000,
        city="Lahore",
        bedrooms_min=3,
        wants_installment=True,
        preferred_amenities=["park"],
        investment_goal="rental_yield",
    )

    print(rank_properties(sample_properties, pref, top_n=2))
