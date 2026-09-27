# TTS Evaluation: Fish Audio vs. ElevenLabs

**Purpose:** Decide the TTS vendor for the RealEstate Hub UrduLish voice agent.
**Note:** Figures below are based on public pricing/docs research as of mid-2026 and should be re-verified against current vendor pages before final commitment, since TTS pricing and latency benchmarks change frequently in this market.

| Criterion | Fish Audio | ElevenLabs | Winner | Notes |
|---|---|---|---|---|
| **Latency (TTFB)** | Sub-150ms on newer models, positioned as one of the fastest streaming options | ~300–500ms typical | **Fish Audio** | Fish Audio is explicitly built around ultra-low-latency streaming, which matters most for live phone calls |
| **Naturalness (UrduLish)** | Decent multilingual quality but Urdu is not one of its core supported languages; code-switching quality unproven | Very strong English naturalness, but similarly lacks native Urdu voices | **Tie / Neither strong** | Neither vendor lists Urdu as a first-class supported language — both will need testing and likely a custom/cloned voice for acceptable UrduLish delivery |
| **Emotion/expressiveness** | Supports inline emotion tags (angry, sad, excited, whispering, etc.) for direct delivery control | Strong preset "styles," widely regarded as the most expressive mainstream TTS | **ElevenLabs** (slightly), Fish Audio close behind | ElevenLabs' expressiveness is best-in-class for English; Fish Audio's tag-based control is a capable, cheaper alternative |
| **Streaming support** | Yes, native low-latency streaming | Yes, native streaming | **Tie** | Both support the streaming architecture this project needs |
| **Voice cloning quality** | Clone from ~10–15 seconds of reference audio; large community voice library | Instant + professional cloning tiers, generally considered top-tier quality | **ElevenLabs** (quality edge), Fish Audio (cost edge) | ElevenLabs clones are typically rated higher fidelity; Fish Audio cloning is far cheaper and "good enough" for many use cases |
| **Pricing (per 1M chars)** | Roughly $15/1M characters, pay-as-you-go, no subscription required | Roughly $120–$300+/1M characters equivalent depending on tier | **Fish Audio** | Fish Audio is meaningfully cheaper — commonly cited as 50–70% lower API cost than ElevenLabs at comparable volume |
| **Multilingual coverage** | ~10 languages (English, Chinese, Japanese, Korean, Spanish, French, German, Russian, Arabic, Portuguese) | 29+ languages, broader mainstream coverage | **ElevenLabs** | ElevenLabs has broader out-of-the-box language coverage |
| **Urdu pronunciation** | No native Urdu voice; would rely on Arabic/Hindi-adjacent phoneme handling or a custom-trained/cloned voice | No native Urdu voice either | **Neither — requires custom work** | This is the single biggest open risk for both vendors and must be tested with real UrduLish sample scripts before committing |
| **Urdu-English code-switching** | Unverified; multilingual model architecture may handle mixed input better than single-language-locked systems | Unverified; ElevenLabs' models are typically tuned per selected language, which can penalize mixed-language input | **Fish Audio (likely, untested)** | Needs a hands-on pilot test with actual UrduLish scripts from `docs/urdu_lish_persona.md` before deciding |

---

## Recommendation

**Fish Audio is the stronger fit for this project's Day-1 constraints** — its lower per-character cost (roughly 5–10x cheaper than ElevenLabs at this project's expected call volume) and sub-150ms latency directly support the real-time phone-call use case and a cost-sensitive Pakistani SME budget. However, neither vendor has native Urdu support, so **the deciding factor should be a hands-on pilot**: generate the same UrduLish phrase-bank samples (Task 3) through both APIs and have native Urdu speakers on the team rate naturalness and code-switching quality before locking in the vendor. If Fish Audio's UrduLish output tests acceptably, its cost and latency advantages make it the default recommendation; if quality is unacceptable, ElevenLabs' broader language tooling and higher cloning fidelity become the fallback despite the higher cost.
