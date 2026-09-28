# User Guide — RealEstate Hub AI Voice Agent

## Requirements
- Chrome, Edge, or Firefox (latest)
- Microphone permission for voice input
- Working internet (Whisper via Groq, Calendar + Gmail APIs)

## Starting a conversation
1. Open the demo URL (Streamlit: `http://localhost:8501`; WebSocket client: `http://localhost:8000`)
2. Click **Start Call** (WebSocket UI) or just use the chat box (Streamlit UI)
3. Type in English, Urdu, or UrduLish — the agent understands all three
4. The agent replies in UrduLish and speaks the reply back

## What you can ask
- Property searches: *"I want 3 bedroom houses in Lahore"*
- Refinements: *"Us se sasti koi option?"*
- FAQs: *"DHA Phase 5 mein schools kaunse hain?"*
- Price questions: *"LAH-0013 ki price kya hai?"*

## Booking a site visit
Say or type a booking request with the property ID, e.g.:
- *"Book visit for LAH-0013"*

The agent then asks, turn by turn, for:
1. Your full name
2. Your confirmation email
3. Preferred date and time (format: `YYYY-MM-DD HH:MM`, e.g. `2026-10-05 15:00`)

After all four are collected, the agent asks **haan / nahi** to confirm. Reply `haan` and it will:
- Create the Calendar event
- Email the confirmation
- Reply with the confirmation text

## Rescheduling or cancelling
Say *"reschedule"* or *"cancel"* followed by the new date/time or the property ID. The agent will confirm before making any changes.

## Barge-in (WebSocket UI)
Press **Escape** while the agent is speaking to interrupt it mid-sentence.

## If something goes wrong
- **No response**: check your mic permission, then try typing instead
- **"Technical issue" message**: the LLM or retriever had a transient error — retry
- **Booking fails**: check the terminal — Calendar/email credentials may need refreshing
- **Wrong transcript**: Whisper works best on English; repeat slowly or type

## Privacy
- Voice audio is sent to Groq Whisper for transcription (not stored beyond the request)
- Conversation text is kept in the running process's memory only (reset on restart)
- Bookings create a Calendar event visible to the agent's Google account
- Confirmation emails are sent to the address you provide