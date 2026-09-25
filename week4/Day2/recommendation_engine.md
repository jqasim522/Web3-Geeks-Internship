# Recommendation Engine — Day 2

## Scoring Objective
Rank properties against user needs while keeping hard constraints explicit and auditable.

## Input Dimensions
- Budget (`price_pkr`)
- City + area preference
- Bedrooms (or commercial size proxy)
- Purpose (sale/rent/investment)
- Amenities preferences
- Investment goal (capital gain vs rental yield)
- Installment preference

## Weight Model
| Component | Weight | Rationale |
|---|---:|---|
| Budget Fit | 0.35 | Biggest decision driver in Pakistani market |
| Location Fit | 0.25 | City/area mismatch kills conversion early |
| Property Spec Fit (beds/type/size) | 0.20 | Practical usability and household match |
| Installment/Payment Fit | 0.10 | Important for affordability-sensitive leads |
| Amenities Fit | 0.05 | Useful tie-breaker due to sparse data |
| Investment Goal Fit | 0.05 | Adds investor context without overriding hard facts |

Total = 1.00

## Guardrails
- Hard filters apply before scoring: unavailable listings, wrong purpose, and over-max budget outliers excluded.
- Missing data never gets fabricated; missing amenities contribute neutral score.
- Every recommendation carries component-wise score breakdown.

## Example Interpretation
- 0.85+ : Strong match
- 0.70–0.84 : Good match
- 0.55–0.69 : Conditional match (explain tradeoffs)
- <0.55 : Do not recommend unless user explicitly broadens constraints

## Decisions & Tradeoffs
- Weighted model chosen over opaque ML ranking to keep explanations and QA straightforward.
- Kept amenities low-weight because seed coverage is sparse.
- Enforced hard-filter-first strategy to prevent persuasive but invalid suggestions.

## Risks & Mitigations
- **Risk:** Fixed weights may underfit niche user behavior.  
  **Mitigation:** calibrate weights using Day 6 conversation outcomes.
- **Risk:** Sale-only dataset can skew investment recommendations.  
  **Mitigation:** include explicit disclosure and capture unmet rental intent.
- **Risk:** Area spelling mismatch can reduce location score unfairly.  
  **Mitigation:** normalize + alias area names before scoring.
