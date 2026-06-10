# Walkthrough video script (~5–6 min)

A beat-by-beat script for the narrated demo. Adapt the wording to your voice — the
structure follows Xeno's suggested sections. Have the app pre-seeded and both services
running before you hit record.

> **Pre-flight:** seed the DB, start channel service (8001), CRM (8000) with a Gemini key,
> and the web app (5173). Open on the **AI Copilot** tab. Have one campaign already launched
> a minute earlier so you can show a *completed* funnel if the live one is still filling.

---

## 0:00 – 0:30 · Product intro (what & why)
- "This is **Reach**, an AI-native mini CRM. The problem: a marketer at a beauty brand like
  SUGAR Cosmetics knows *who* they want to win back, but turning that into a real campaign —
  segment, copy, channel, tracking — is slow and technical."
- "My bet: the marketer should just **talk to an agent**, not fill out forms. I committed to a
  chat-first, agentic product backed by a real analytics dashboard."

## 0:30 – 2:00 · Functional demo (show it working)
- On **AI Copilot**, type: _"Win back customers who bought lipstick but haven't ordered in 60 days."_
- Narrate as the agent works: "It **previewed the audience** — 314 shoppers — **drafted
  personalized copy**, **recommended WhatsApp**, and **staged a draft campaign**. Notice it
  did *not* send anything — it's waiting for me."
- Click **Approve & Launch**. "That human approval is enforced in the API, not just the UI."
- Land on the **campaign detail**. "Now the funnel fills **live** — sent, delivered, opened,
  read, clicked, converted — and attributed revenue ticks up. Each recipient's state is here."
- Briefly hop to **Segments** and **Customers**: "Everything the agent created is inspectable —
  nothing's a black box."

## 2:00 – 3:00 · Technical architecture
- Show the README architecture diagram.
- "Two independently deployable services. The **CRM** is the product. The **channel service**
  is a stub of a messaging provider — it delivers nothing, it *simulates* the lifecycle and
  **calls back**."
- "When I launch, the CRM materialises one communication per recipient and POSTs an
  **HMAC-signed batch** to the channel service, which returns 202 immediately."
- "The channel service runs a **bounded queue + worker pool** for intake, and a **separate
  semaphore** capping concurrent callbacks. It deliberately sends events **out of order** and
  injects **duplicates**, with **retry/backoff** — because that's what real delivery looks like."

## 3:00 – 4:00 · Code walkthrough (two key parts)
- **Filter DSL** (`segmentation/dsl.py`): "The agent never writes SQL. It emits a validated
  JSON filter that compiles to a parameterised query — no injection, no hallucinated columns,
  and it runs on both SQLite and Postgres because dates are handled in Python."
- **Idempotent receipts** (`services/receipts.py` + `models.py`): "A communication's status is
  **derived from its timestamps**, and every event has a **unique id**. So duplicates are
  no-ops, out-of-order events still produce the right funnel, and revenue is never
  double-counted. Here are the tests proving exactly that." (show `pytest` green.)

## 4:00 – 5:00 · AI-native workflow
- "Two senses of AI-native. **In the product:** the agent is a bounded tool-use loop where
  tools are the only way it touches the CRM, and there's deliberately **no launch tool** — a
  human approves every send. The LLM sits behind a swappable provider interface, defaulting to
  free-tier Gemini 2.5 Flash."
- "**In how I built it:** I used an AI coding agent to scaffold both services, generate the
  DSL compiler and the idempotent receipt handler, and write the tests — but I directed and
  reviewed each piece against real output. For example, my first worker blocked throughput by
  holding a worker for each message's full lifecycle; I caught it on a load test and refactored
  to the queue-plus-semaphore design you saw."

## 5:00 – 5:30 · Close
- "A working, deployed product is the baseline. Where I tried to stand out: a sharp,
  opinionated chat-first scope; a production-shaped callback loop with idempotency I can prove;
  and explicit tradeoffs for what I'd change at scale — all in the README. Thanks for watching."

---

### Things to make sure are on screen at some point
- [ ] The agent staging a campaign **without** sending (draft state)
- [ ] The **Approve & Launch** click
- [ ] The **live funnel** moving
- [ ] **Attributed revenue** number
- [ ] `pytest` passing
- [ ] The architecture diagram
