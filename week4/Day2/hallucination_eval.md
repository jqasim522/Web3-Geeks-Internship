# Hallucination Evaluation — Day 2

## Evaluation Setup
- 20 UrduLish user questions across price, availability, installment, possession, and location filters.
- Ground truth from SQLite (`data/realestate.db`) + retrieved docs.
- Scored outputs on:
  - Grounding Rate (answer supported by retrieved/SQL evidence)
  - Retrieval Accuracy (correct supporting context fetched)
  - Hallucination Rate (claims not in evidence)

## Per-Question Results
| # | Query Type | Grounded | Retrieval Correct | Hallucination |
|---:|---|---|---|---|
| 1 | budget+city | Yes | Yes | No |
| 2 | installment availability | Yes | Yes | No |
| 3 | DHA area query | Yes | Yes | No |
| 4 | possession timeline | Yes | Yes | No |
| 5 | transfer FAQ | Yes | Yes | No |
| 6 | NOC FAQ | Yes | Yes | No |
| 7 | maintenance FAQ | Yes | Yes | No |
| 8 | developer reputation | Yes | Yes | No |
| 9 | bedrooms filter | Yes | Yes | No |
| 10 | luxury segment | Yes | Yes | No |
| 11 | low-budget options | Yes | Yes | No |
| 12 | no-match strict filter | Yes | Yes | No |
| 13 | amenity request | Yes | Partial | No |
| 14 | ROI expectation | Yes | Yes | No |
| 15 | comparison ask | Yes | Yes | No |
| 16 | schedule visit ask | Yes | Yes | No |
| 17 | source verification | Yes | Yes | No |
| 18 | off-catalog rental ask | Yes | Yes | No |
| 19 | edge case area alias | Yes | Partial | No |
| 20 | ambiguous possession ask | No | Yes | Yes |

## Aggregated Metrics
| Metric | Value |
|---|---:|
| Grounding Rate | 95% (19/20) |
| Retrieval Accuracy | 90% (18/20) |
| Hallucination Rate | **5% (1/20)** |

## Root Cause (failure case #20)
- Query used ambiguous possession phrasing without explicit project reference.
- Retrieved FAQ context dominated over property-specific constraints.
- Generator inferred timeline language too confidently.

## Remediation Applied
1. Add ambiguity detector: possession answers require project/property identifier.
2. If missing identifier, respond with clarifying question instead of timeline estimate.
3. Increase retriever priority for SQL-linked property context on possession intents.

## Results Table (Acceptance)
| Acceptance Criterion | Target | Observed | Status |
|---|---:|---:|---|
| Hallucination Rate | <= 5% | 5% | Pass |
| Grounding Rate | >= 90% | 95% | Pass |

## Verdict
Day 2 pipeline meets the hallucination acceptance threshold, with one clearly root-caused ambiguity failure.

## What I'd change in v2
- Increase eval set from 20 to 100+ with paraphrase/noise variants.
- Add automatic evidence citation check in test harness.
- Add intent-specific confidence thresholds before generation.
