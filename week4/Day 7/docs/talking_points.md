# Talking Points

STATUS: CODE-COMPLETE — presenter notes to accompany `docs/presentation.md`.

General rule throughout: emphasize what's **verified** (Days 2-5, with
real numbers) versus what's **pending** (Day 6 test execution) — don't let
the two blur together in how you talk about it, even informally.

## Slide-by-slide

### Title
- Mentor audience: mention this is a 7-day sprint, so scope tradeoffs were
  deliberate, not oversights.
- Client audience: keep this to one sentence — who you are, what you built.

### Problem (1-2)
- Client audience: lean on the WhatsApp-exchange example — it's the most
  relatable pain point.
- Mentor audience: you can go faster here; they already know the brief.

### Solution
- Emphasize "real" — real dataset, real calendar, real email — this
  distinguishes it from a chatbot demo with canned responses.
- **Don't say:** "it understands anything you say" — it's tuned for real
  estate intents; say "handles the real estate conversations we tested for
  across normal, edge-case, and adversarial scenarios."

### Architecture / Tech stack
- Mentor audience: they'll want to know *why* Groq→Gemini→template, not
  just that it exists — one sentence: "cost and latency first, with a
  never-fails template tier as the floor."
- Client audience: keep this slide brief verbally; the diagram carries it.

### Demo
- Transition sentence: "Rather than describe it, let me show you." Move
  straight into `docs/demo_script.md`.

### Results (1-2)
- **What to emphasize:** every number on these slides is from a real run,
  not an estimate — say so once, explicitly, then let the numbers speak.
- **What NOT to say:** don't round the Day 6 placeholders into an implied
  number ("mostly passing," "should be fine") — say plainly that Day 6
  execution is still pending.
- Transition into Limitations: "That said, here's what we haven't
  verified yet."

### Limitations
- This is the slide most likely to build trust with a technical mentor —
  don't rush it or apologize for it.
- **What NOT to say:** don't frame Day 6 being unrun as a completed
  feature ("the tests are ready to go!") — frame it accurately as
  "written, not yet executed against production code."

### Future Work
- Client audience: translate technical items into business terms — e.g.
  "add login/authentication" becomes "restrict who can use the booking
  system."

### Q&A
- Transition: "I've tried to anticipate the hard questions — happy to take
  whatever's actually on your mind first."

### Thank You
- Don't over-explain; end on the contact slide and open the floor.

## What NOT to say, generally

- Don't say "production-ready" — say "deployment-ready configuration,
  pending Day 6 execution and a security review of the live findings."
- Don't say "fully tested" — say "extensively test-*written*, partially
  test-*executed*" and point to the real Day 2-5 numbers as the executed
  part.
- Don't invent or round any number not listed in `docs/presentation.md` —
  if asked for a number not on that list, say "I don't have that
  measured yet" rather than estimating live.
