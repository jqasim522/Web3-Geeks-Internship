> **Global fallback (applies to all flows):** If the caller hangs up at any point, the orchestrator logs the partial conversation state (name, phone if captured, intent, last question asked) so the team can follow up. This is handled at the telephony/orchestrator layer and is not repeated in each flowchart below.


# Conversation Flow Design

**Project:** RealEstate Hub — AI Voice Agent
Each flow below lists entry condition, decision points, success exit, and failure/fallback exit, followed by a Mermaid flowchart.

---

## 1. Buyer Inquiry

- **Entry condition:** Inbound call, no existing profile match, caller intent = buying a property.
- **Decision points:** Intent confirmed? Budget stated? Location stated? Bedroom count stated? Matching inventory found?
- **Success exit:** Recommendation given → visit booked → confirmation sent.
- **Failure/fallback exit:** No matching inventory → offer closest alternatives or human callback. Caller hangs up at any point → log partial data for follow-up.

```mermaid
flowchart TD
    A[Greeting] --> B{Intent: Buying?}
    B -- Yes --> C[Ask Budget]
    B -- No / Unclear --> B1[Clarify Intent] --> B
    C --> D[Ask Preferred Location]
    D --> E[Ask Bedrooms Required]
    E --> F{Matching Properties Found?}
    F -- Yes --> G[Present Recommendation]
    F -- No --> F1[Offer Closest Alternatives]
    F1 --> G2{Caller Interested?}
    G2 -- No --> H2[Offer Human Callback] --> Z[End - Logged]
    G2 -- Yes --> G
    G --> H{Wants to Book Visit?}
    H -- Yes --> I[Collect Name/Phone/Date/Time]
    I --> J[Check Availability]
    J --> K[Confirm Booking]
    K --> L[Send Confirmation]
    L --> Z2[End - Success]
    H -- No --> M[Offer to Send Details via WhatsApp]
    M --> Z2
    
```

---

## 2. Rental Inquiry

- **Entry condition:** Inbound call, intent = renting.
- **Decision points:** Rent range stated? Area stated? Move-in date stated? Match found?
- **Success exit:** Recommendation → visit booked.
- **Failure/fallback exit:** No match within rent range → widen range or offer callback; caller becomes frustrated → escalate.

```mermaid
flowchart TD
    A[Greeting] --> B{Intent: Renting?}
    B -- Yes --> C[Ask Rent Range]
    B -- No --> B1[Clarify Intent] --> B
    C --> D[Ask Preferred Area]
    D --> E[Ask Move-in Date]
    E --> F{Matching Rentals Found?}
    F -- Yes --> G[Present Recommendation]
    F -- No --> F1{Widen Rent Range?}
    F1 -- Yes --> C
    F1 -- No --> H1[Offer Human Callback] --> Z1[End - Logged]
    G --> H{Wants to Book Visit?}
    H -- Yes --> I[Collect Name/Phone/Date/Time]
    I --> J[Check Availability]
    J --> K[Confirm Booking + Send Confirmation]
    K --> Z2[End - Success]
    H -- No --> M[Offer Details via WhatsApp] --> Z2
    G --> N{Caller Frustrated/Angry?}
    N -- Yes --> O[Apologize + Human Callback] --> Z1
```

---

## 3. Commercial Property Inquiry

- **Entry condition:** Inbound call, intent = commercial space.
- **Decision points:** Business type stated? Square footage needed? Location? Lease terms acceptable?
- **Success exit:** Recommendation → visit booked.
- **Failure/fallback exit:** No suitable commercial listing → callback; lease terms mismatch → note requirement and offer follow-up.

```mermaid
flowchart TD
    A[Greeting] --> B{Intent: Commercial?}
    B -- Yes --> C[Ask Business Type]
    B -- No --> B1[Clarify Intent] --> B
    C --> D[Ask Required Sq. Ft.]
    D --> E[Ask Preferred Location]
    E --> F[Present Available Options]
    F --> G{Lease Terms Acceptable?}
    G -- Yes --> H[Present Recommendation]
    G -- No --> G1[Note Requirement] --> G2[Offer Human Follow-up] --> Z1[End - Logged]
    H --> I{Wants to Book Visit?}
    I -- Yes --> J[Collect Name/Phone/Date/Time]
    J --> K[Check Availability]
    K --> L[Confirm Booking + Send Confirmation]
    L --> Z2[End - Success]
    I -- No --> M[Offer Details via WhatsApp] --> Z2
    F --> N{No Options Available?}
    N -- Yes --> G2
```

---

## 4. Investment Inquiry

- **Entry condition:** Inbound call, intent = investment.
- **Decision points:** Investment size stated? ROI expectations stated? Suitable project found?
- **Success exit:** Recommended projects → visit/consultation booked.
- **Failure/fallback exit:** ROI expectations unrealistic → soft objection handling (max 2 attempts) then human callback.

```mermaid
flowchart TD
    A[Greeting] --> B{Intent: Investment?}
    B -- Yes --> C[Ask Investment Size]
    B -- No --> B1[Clarify Intent] --> B
    C --> D[Ask ROI Expectations]
    D --> E{Expectations Realistic?}
    E -- Yes --> F[Present Recommended Projects]
    E -- No --> E1[Soft Objection Handling - Attempt 1] --> E2{Still Unrealistic?}
    E2 -- Yes --> E3[Soft Objection Handling - Attempt 2] --> E4{Still Unrealistic?}
    E4 -- Yes --> H1[Offer Human Callback] --> Z1[End - Logged]
    E4 -- No --> F
    E2 -- No --> F
    F --> G{Wants Visit/Consultation?}
    G -- Yes --> I[Collect Name/Phone/Date/Time]
    I --> J[Check Availability]
    J --> K[Confirm Booking + Send Confirmation]
    K --> Z2[End - Success]
    G -- No --> M[Offer Investment Brochure via WhatsApp] --> Z2
```

---

## 5. Returning Customer

- **Entry condition:** Caller's phone number matches an existing profile.
- **Decision points:** Past context relevant to current call? New requirement stated?
- **Success exit:** Personalized recommendation based on history → booking or follow-up.
- **Failure/fallback exit:** Caller's needs have changed entirely → treat as new inquiry (route into Flow 1–4).

```mermaid
flowchart TD
    A[Personalized Greeting - Use Name] --> B[Recall Past Context]
    B --> C{Same Requirement as Before?}
    C -- Yes --> D[Confirm Status/Update]
    D --> E[Present Updated Recommendation]
    C -- No --> F[Ask New Requirement]
    F --> G{Requirement Type}
    G -- Buy/Rent/Commercial/Invest --> H[Route to Matching Flow]
    E --> I{Wants to Book Visit?}
    I -- Yes --> J[Collect/Confirm Name/Phone/Date/Time]
    J --> K[Check Availability]
    K --> L[Confirm Booking + Send Confirmation]
    L --> Z[End - Success]
    I -- No --> M[Offer Details via WhatsApp] --> Z
    H --> Z2[End - Handed to Flow 1-4]
```

---

## 6. Appointment Rescheduling

- **Entry condition:** Caller wants to change an existing booking.
- **Decision points:** Existing booking identified? New time available?
- **Success exit:** Booking updated → confirmation sent.
- **Failure/fallback exit:** Booking not found → escalate; no availability at new time → offer alternatives.

```mermaid
flowchart TD
    A[Greeting] --> B[Ask for Booking Reference / Name+Phone]
    B --> C{Booking Found?}
    C -- No --> C1[Apologize] --> C2[Offer Human Callback] --> Z1[End - Logged]
    C -- Yes --> D[Confirm Existing Booking Details]
    D --> E[Ask Preferred New Time]
    E --> F{New Time Available?}
    F -- Yes --> G[Update Booking]
    G --> H[Send Updated Confirmation]
    H --> Z2[End - Success]
    F -- No --> I[Offer Alternative Times]
    I --> J{Caller Accepts Alternative?}
    J -- Yes --> G
    J -- No --> C2
```

---

## 7. Appointment Cancellation

- **Entry condition:** Caller wants to cancel an existing booking.
- **Decision points:** Booking identified? Reason captured? Reschedule offered?
- **Success exit:** Cancellation logged; reschedule offered as soft save.
- **Failure/fallback exit:** Booking not found → escalate.

```mermaid
flowchart TD
    A[Greeting] --> B[Ask for Booking Reference / Name+Phone]
    B --> C{Booking Found?}
    C -- No --> C1[Apologize] --> C2[Offer Human Callback] --> Z1[End - Logged]
    C -- Yes --> D[Confirm Existing Booking Details]
    D --> E[Ask Reason for Cancellation]
    E --> F[Process Cancellation]
    F --> G{Offer Reschedule Instead?}
    G -- Caller Accepts --> H[Route to Reschedule Flow]
    G -- Caller Declines --> I[Log Cancellation + Reason]
    I --> J[Send Cancellation Confirmation]
    J --> Z2[End - Success/Logged]
    H --> Z3[End - Handed to Flow 6]
```
