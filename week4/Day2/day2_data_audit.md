# Day 2 Data Audit — `properties_normalized.csv`

## Source
- Canonical seed: `/home/runner/work/Web3-Geeks-Internship/Web3-Geeks-Internship/week4/Day2/properties_normalized.csv`
- Rows: **575**
- Columns: **17**

## Schema Snapshot
| Column | Type | Non-Null | Nulls |
|---|---|---:|---:|
| property_id | string | 575 | 0 |
| city | string | 575 | 0 |
| area | string | 575 | 0 |
| property_type | string | 575 | 0 |
| purpose | string | 575 | 0 |
| bedrooms | float64 | 557 | 18 |
| bathrooms | float64 | 557 | 18 |
| size_sqft | int64 | 575 | 0 |
| area_sqft_normalized | float64 | 575 | 0 |
| price_pkr | int64 | 575 | 0 |
| price_formatted | string | 575 | 0 |
| developer | string | 575 | 0 |
| has_installment_plan | bool | 575 | 0 |
| description | string | 575 | 0 |
| source_url | string | 575 | 0 |
| amenities | string | 213 | 362 |
| qa_flags | string | 52 | 523 |

## Sample Integrity
- `property_id` and `source_url` are unique in the seed (575/575).
- Pricing and size are present for all listings (`price_pkr`, `size_sqft`, `area_sqft_normalized` complete).
- Core geo granularity exists at city + area text level.

## Unique-Value Summary (categorical)
| Field | Unique Values | Notes |
|---|---:|---|
| city | 4 | Karachi, Lahore, Rawalpindi, Islamabad |
| area | 295 | Broad locality spread; duplicates expected by market demand |
| property_type | 8 | House dominates inventory |
| purpose | 1 | Only `Sale` present |
| developer | 5 | `Private / Unknown` is largest bucket |
| amenities | 38 | Sparse and inconsistent coverage |
| qa_flags | 11 | Quality exceptions concentrated in a small subset |

## Null / Missing Analysis
- `bedrooms` + `bathrooms`: missing primarily on non-residential/other records.
- `amenities`: high sparsity (63%) and non-standard tagging format.
- `qa_flags`: intentionally sparse exception field; blank means no rule hit.

## Explicit Gaps to Augment (without replacing seed)
1. Add recommender-ready derived fields: `price_per_sqft`, `size_marla_est`, `listing_status`, `installment_plan_months`, `possession_timeline_months`.
2. Add normalized search fields for UrduLish retrieval (`city_normalized`, `area_normalized`).
3. Expand surrounding KB entities absent from seed: FAQs, developer reputation notes, project-level context.
4. Add operational availability fields in SQLite layer to enforce no-hallucination routing.
5. Add structured joins for schools/hospitals/payment-plan metadata as Day 2 knowledge entities.

## Decisions & Tradeoffs
- Kept seed rows immutable as source-of-truth and added enrichments in downstream artifacts only.
- Did not impute missing bedrooms/bathrooms blindly to avoid contaminating structured decision logic.
- Used sparse amenities as optional signal instead of hard filter because coverage is incomplete.

## Risks & Mitigations
- **Risk:** Sparse amenities can bias recommendations.  
  **Mitigation:** Weight amenities lower than budget/location match and use soft scoring.
- **Risk:** `purpose` only includes sale inventory while future flows include rentals.  
  **Mitigation:** Route rental intents to graceful fallback/human callback until rental rows are ingested.
- **Risk:** Free-text area naming variants can fragment search.  
  **Mitigation:** Maintain normalized area slug and alias mapping in retrieval pre-processing.
