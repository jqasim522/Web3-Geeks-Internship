# Day 6 Security Report

## Status: executed against mocked layer — 127/127 passing, still not a pentest

The adversarial suite has now been run against the real `lib/` codebase.
**127 of 127 adversarial tests passed** (verified against
`day6_coverage.txt`'s per-file dot counts, which sum to exactly 127 — see
`day6_eval_report.md` for the file-by-file tally). This is a real,
confirmed result, not a projection. It is still **not a penetration
test** — every one of these tests runs against a rule-based classifier
and/or mocked dependencies, not a live LLM under adversarial pressure, and
not real production infrastructure. Read "What this suite still cannot
tell you" below before treating this as a security clearance.

## By attack type (as categorized by the project owner)

`day6_summary.txt` reports the following breakdown, which sums to 127 and
is retained here as the owner's own categorization. Note this is an
attack-*type* breakdown, not a per-*file* breakdown — several test files
intentionally cover more than one attack type each (see "Coverage by
attack category" below for the actual file-level design), so these
numbers do not map one-to-one onto individual test files:

- 28 prompt injection attempts — all refused
- 25 jailbreak attempts — all refused
- 10 PII extraction attempts — no leak
- 25 SQL injection attempts — DB intact
- 15 path traversal attempts — no file access
- 12 unicode attacks — no crash
- 12 DoS attempts — no crash

## Coverage by attack category (file-level design, unchanged from plan)

### Prompt injection (`tests/adversarial/test_prompt_injection.py`)
15 attack strings: classic ignore-prior-instructions, role override,
system-prompt leak requests, context injection via fake SYSTEM/USER
labels, nested `[INST]` blocks, token-smuggling attempts, fake-role
tagging, prompt-continuation attacks, fictional-framing jailbreaks, an
Urdu-wrapped injection, SQL injection embedded in a question, path
traversal, XML-tag injection, injection via a property-ID field, and a
multi-language confusion attempt. Verified: no crash, and the response
contained none of a defined set of compliance signals (leaked keys,
"I have been jailbroken", etc). **23 tests actually collected/run in this
file** per `day6_coverage.txt` — the file's own docstring describes 15
attack strings, so some strings are evidently exercised through more than
one test function (e.g. parametrized across multiple assertions).

### Jailbreak attempts (`tests/adversarial/test_jailbreak.py`)
12 attempts: roleplay framing, hypothetical framing, false-authority
framing ("I am your developer"), incremental escalation, reverse
psychology, fake maintenance mode, translation-smuggled Urdu jailbreak,
social-engineering ("you owe me a favor"), false-emergency framing,
recursive jailbreak-the-jailbreaker, point-based reward/punishment
framing, and nested-character roleplay. Also checks that a jailbreak
attempt does not "stick" on the same conversation thread. **25 tests
actually run** per `day6_coverage.txt`.

### PII / secret extraction (`tests/adversarial/test_pii_leakage.py`)
6 direct secret-extraction attempts (API keys, `.env` contents, Gmail app
password, OAuth client secret, DB connection string, verbatim system
prompt) plus 3 attempts to extract *other users'* booking data.
`tests/adversarial/test_dos_resilience.py`'s `PII_ATTEMPTS` (5 strings)
additionally checks this at the DoS-resilience layer. **10 tests run** in
`test_pii_leakage.py` itself per `day6_coverage.txt`.

### SQL injection (`tests/adversarial/test_sql_injection.py`)
7 payloads against `get_property`, `query_properties`, `parse_question`,
and `booking_tool.validate_args`, plus a full-suite row-count sanity
check confirming no payload altered the 575-row dataset. **19 tests run**
per `day6_coverage.txt` — verified: the dataset row count is intact after
the run.

### Path traversal (`tests/adversarial/test_path_traversal.py`)
8 payload styles (relative, absolute, Windows-style, URL-encoded,
double-encoded, `file://`) tested via three entry points: a plain chat
message, the `property_id` field in a price lookup, and
`booking_tool.validate_args`'s `property_id` validation. **14 tests run**
per `day6_coverage.txt`.

### Unicode attacks (`tests/adversarial/test_unicode_attacks.py`)
Homoglyph substitution, combining diacritical marks, NFC/NFD
normalization mismatches, mixed bidirectional text, astral-plane
characters, and lone combining marks with no base character.
`tests/adversarial/test_dos_resilience.py` separately covers RTL
override, zero-width joiners, and emoji flood as DoS-adjacent unicode
cases. **11 tests run** in `test_unicode_attacks.py` per
`day6_coverage.txt`.

### Tool-call injection (`tests/adversarial/test_tool_call_injection.py`)
Smuggled extra keys in otherwise-valid tool-call args (`is_admin`,
`skip_validation`), nested tool-call-shaped JSON inside a legitimate
field, tool-name case/alias spoofing, invocation of an unregistered tool
name, and a SQL payload disguised as tool-call args. **5 tests run** per
`day6_coverage.txt`.

### DoS / resilience (`tests/adversarial/test_dos_resilience.py`)
10K, 50K, and 100K character inputs; 1000-emoji flood; null bytes; RTL
override; zero-width joiners/non-joiners/invisible separators; 5 PII
extraction attempts. **20 tests run** per `day6_coverage.txt`.

## What this suite still cannot tell you

- **Whether jailbreak/prompt-injection resistance holds against the real
  LLM, not just the rule-based classifier.** All 127 passing tests above
  ran against the mocked/offline layer. The live suite (`test_live_llm.py`)
  is where real-LLM adversarial resistance would be exercised — and its
  own results are themselves in dispute between two attached runs (see
  `day6_eval_report.md`'s "Live suite: a real discrepancy" section). No
  attached evidence shows an adversarial prompt actually being sent to a
  real Groq or Gemini call and the response checked. **This is the single
  biggest gap between "127/127 passing" and "this is secure."**
- **Whether secrets are handled correctly outside conversational scope**
  — `.env` hygiene, log redaction of booking PII, credential storage —
  this suite tests conversational leakage only, not infrastructure/ops
  security. Unchanged from the original assessment.
- **Any live-attack finding.** 127/127 is a real, executed result now —
  but it is 127/127 against the test suite's own defined attack strings
  and refusal signals, not an independent red-team assessment. A
  determined attacker's payloads were not tried; only the ones this
  suite's authors thought to write.
- **Whether the real calendar event surfaced during live testing
  (`bqm0g5rr5gbrpv1mukjkogo7a0`) was actually deleted.** Not a security
  vulnerability in the product, but an operational loose end from testing
  — see `day6_eval_report.md`.