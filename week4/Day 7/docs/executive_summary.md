# Executive Summary — Pakistani Real Estate Voice Agent

*One page, for a non-technical stakeholder.*

## What it does

A conversational assistant that lets a real estate client search
properties, ask about prices, and book a site visit — by speaking or
typing in Roman Urdu, Urdu, or English — without a human agent handling
every routine question. When a client wants a site visit, the assistant
checks a real calendar for availability, books it, and sends a
confirmation email automatically.

## Why it matters

Clients today reach agents through informal channels (calls, WhatsApp) and
wait for a human to answer basic questions — availability, pricing,
scheduling — that follow a predictable pattern. Automating that first
layer of conversation means faster responses for clients and fewer
repetitive questions for agents, while keeping a consistent, recorded
trail of what was promised (a real calendar event, a real email) rather
than an informal verbal exchange.

## What's been verified so far

- **575** real property listings loaded and searchable
- **100%** accuracy on a 20-question retrieval test suite
- **18/18** and **15/15** (two separate test rounds) conversational
  scenarios passing
- A real booking was completed end-to-end in testing: a real calendar
  event created, a real confirmation email delivered
- **15 out of 15** test conversations passed using the live AI service,
  not just a simulated one

## What's not yet finished

A broader round of testing — covering unusual inputs, attempted misuse,
and how the system behaves if a service (calendar, email, AI provider)
goes down mid-conversation — has been written but **not yet run** against
the finished system. Until that run happens, "how well does it handle the
unexpected" doesn't have a confirmed answer yet, even though the core
conversation flow is verified working.

Additionally, the system as configured does not yet restrict who can use
it — before it's opened up publicly, an access-control step is needed.

## Cost per call (estimate)

**[FILL IN: no per-call cost figure exists yet — this depends on actual
usage volume against the AI provider, voice provider, and hosting costs
once running. Fill in once real usage data or provider quotes are
available.]**

## Time saved (estimate)

**[FILL IN: no measured baseline exists yet for how long a human agent
currently spends on these routine queries. Estimate once compared against
real agent time logs, or state a target assumption explicitly if
presenting before that data exists.]**

### Deployment notes

Docker infrastructure is fully specified: `deploy/Dockerfile`, `deploy/docker-compose.yml`,
`deploy/nginx.conf`, and systemd unit files are included and cover image build,
runtime orchestration, reverse-proxy setup, and service management.

Live Docker build was not exercised on the development machine because
hardware-assisted virtualization (Intel VT-x / AMD-V) is disabled in BIOS.
Enabling it requires a BIOS setting change that is outside the project scope.
The application runs fully on the local development stack (FastAPI + Streamlit),
which is what the demo uses.

## What's next

1. Run the outstanding round of testing against the finished system.
2. Add access control before any public/client-facing launch.
3. Deploy to a live server (configuration is ready — see the deployment
   runbook) and monitor real usage for a short pilot period before full
   rollout.
