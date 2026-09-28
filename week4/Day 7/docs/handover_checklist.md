# Handover Checklist

STATUS: CODE-COMPLETE — describes what this handover package contains and
what it explicitly does not. No handover meeting, credential transfer, or
training session has actually occurred; this is the checklist to use when
they do.

## What's included

- **Code**: `lib/` (Days 2-5 application code, per the project's own file
  layout), `data/realestate.db` (575 listings), `tests/` (full Day 6 suite
  — see `docs/day6_test_plan.md` for what's verified vs. assumed)
- **Deployment configuration**: `deploy/` — Dockerfile, docker-compose.yml,
  nginx.conf, systemd unit, deploy.sh, `.env.example` (names only, no real
  secrets)
- **Documentation**: this repo's `docs/` — architecture, API, health
  checks, troubleshooting, changelog, plus Day 6's carried-over test plan,
  security report, and eval report
- **Presentation materials**: slide content, demo script, talking points,
  Q&A prep (content only — the user builds the actual slide deck file)
- **This checklist**

## What's NOT included

- **Paid service subscriptions or API credits** — Groq, Gemini, Deepgram/
  AssemblyAI, Fish Audio, a domain name, and cloud hosting are all
  separate accounts/costs the client or owner must hold directly. Nothing
  in this handover transfers or pays for those.
- **Ongoing support beyond the window below** — bug fixes, feature
  requests, or new development after the support window ends are a
  separate engagement.
- **A completed Day 6 test run** — see `docs/day6_eval_report.md`; this is
  written work product, not a passing test report.
- **A signed license decision** — `LICENSE` at the repo root is a
  placeholder with both MIT and proprietary text; pick one.
- **Load testing or a security audit by a third party** — the Day 6
  adversarial suite is internal test coverage, explicitly not a
  penetration test (see `docs/day6_security_report.md`).

## Credentials transfer

How the receiving party gets real API keys and credentials:

1. Do **not** transfer credentials through chat, email body text, or
   committed to git — use a password manager's secure share feature or an
   encrypted channel.
2. The receiving party creates their own accounts for: Groq, Gemini,
   Deepgram/AssemblyAI, Fish Audio, Google Cloud (OAuth for Calendar/
   Gmail), and their chosen hosting provider — using their own billing,
   not the developer's.
3. Fill in `deploy/.env` (never commit it) using `deploy/.env.example` as
   the template of which variable names are needed.
4. Google OAuth credentials JSON goes in `deploy/secrets/` per
   `deploy/README.md`'s step 4 — this file is a credential and should be
   handled with the same care as an API key.

## Training

Suggested 1-hour session outline for whoever will operate this day-to-day:

| Time | Topic |
|---|---|
| 10 min | Walkthrough of `README.md` and where things live |
| 15 min | Live demo of the three scenarios in `docs/demo_script.md` |
| 15 min | Deployment runbook walkthrough (`deploy/README.md`) — even if the developer does the actual first deploy, the operator should see it once |
| 10 min | `docs/TROUBLESHOOTING.md` — the 6 known common issues and their fixes |
| 10 min | Q&A — what happens if X breaks, who to contact, how to check logs |

## Support window

**2 weeks post-handover** for questions and bug fixes related to what was
delivered in Days 1-7, at the terms agreed separately between the intern/
developer and the client. This does not cover new feature requests. Get
the exact terms (paid, unpaid, scope) confirmed in writing outside this
document — none was specified in the Day 1-7 material this handover is
based on.
