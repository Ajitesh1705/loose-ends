# plan.md — "Loose Ends"

A demo build for a simplifiedQ Founding Engineer application.

**Read this whole file before writing code.** Phases are sequential. Each phase has a
Definition of Done. Do not start a phase until the previous one's DoD passes. If you
find yourself wanting to add something not in this file, add it to `NOTES.md` under
"Rejected scope" instead of building it.

---

## 0. What this is and what it must prove

**The product thesis in one line:** unstructured conversation → structured commitment →
time-aware nudge → drafted action.

**The atomic unit is a commitment**: *who promised what, to whom, by when, and is it
slipping?* Every other feature in simplifiedQ's pitch (re-engagement, client tracking,
revenue signals) is a view over that one table. We build the ledger, not the CRM.

**Five non-negotiables.** These are the demo. Everything else is chrome.

1. **Provenance** — every extracted commitment links to the exact character span in the
   source that produced it, clickable, highlighted in context.
2. **Confidence gating** — high-confidence extractions land in the ledger; ambiguous ones
   go to a review queue with the ambiguity *named in words*.
3. **Cross-channel dedupe** — the same promise made on a call and repeated in a
   confirming email resolves to ONE commitment, with a visible merge trail.
4. **Deterministic decay** — "going cold" is computed in plain Python, unit-tested, and
   explainable in a tooltip. The LLM never decides staleness.
5. **Grounded drafts** — the follow-up quotes the specific thing discussed. No "circling
   back."

**Explicitly out of scope, for the entire build:** real OAuth (Gmail/WhatsApp/Calendar),
multi-tenancy, billing, auth beyond a demo cookie, mobile layouts, a contacts/deals/
pipeline UI, a chat-with-your-data box, dark mode, settings pages, onboarding flows.

---

## 1. Stack (match theirs, no substitutions)

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| DB | Postgres 15 + `pgvector` |
| Queue | Postgres-backed job table + one polling worker process. No Redis, no Celery. |
| LLM | **OpenAI** — Responses API, structured outputs (`strict: true` JSON schema) |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dims) |
| Deploy | Vercel (web) + Cloud Run (api + worker) + Cloud SQL. Docker Compose for local. |

### OpenAI usage rules

- Model IDs live in `.env` only: `OPENAI_MODEL_EXTRACT`, `OPENAI_MODEL_DRAFT`,
  `OPENAI_MODEL_EMBED`. Never hardcode a model string in application code. Pick a
  current small model for extraction and a stronger one for drafting; verify the exact
  IDs against OpenAI's model list at build time rather than trusting memory.
- All extraction calls use **structured outputs with a strict JSON schema**. Do not
  parse free text. Do not use `json_mode`.
- Every LLM call goes through one module: `api/app/llm/client.py`. It owns retries
  (exponential backoff, 3 attempts), timeouts, token/latency/cost logging to an
  `llm_calls` table, and a **schema repair pass** (one retry with the validation error
  fed back) before it gives up.
- `temperature=0` for extraction. Higher only for draft generation.
- Cache by `sha256(prompt_version + model + input_text)` in a `llm_cache` table. Demos
  get re-run a lot; caching keeps it fast and cheap.
- Prompts are versioned files in `api/app/prompts/` (e.g. `extract_v3.md`), and the
  version string is stored on every row the call produced. Evals are meaningless
  otherwise.

---

## 2. Repo layout

```
loose-ends/
├── plan.md
├── README.md               # written in Phase 8, opens with "What I didn't build and why"
├── NOTES.md                # decision log + rejected scope, append-only
├── docker-compose.yml
├── api/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models/          # SQLAlchemy
│   │   ├── schemas/         # Pydantic (also the OpenAI JSON schemas)
│   │   ├── llm/
│   │   │   ├── client.py
│   │   │   └── extract.py
│   │   ├── prompts/
│   │   ├── services/
│   │   │   ├── ingest.py
│   │   │   ├── resolve.py   # dedupe/merge — the hard part
│   │   │   ├── decay.py     # pure functions, no I/O, no LLM
│   │   │   └── draft.py
│   │   ├── routers/
│   │   └── worker.py
│   ├── tests/
│   └── migrations/
├── evals/
│   ├── fixtures/           # 30–40 labelled artifacts
│   ├── run_eval.py
│   └── RESULTS.md
└── web/
    └── src/app/            # Next.js
```

---

## 3. Data model (Phase 1 builds this)

```
sources
  id, kind ('call_transcript'|'email_thread'|'whatsapp_export'|'session_note'),
  title, raw_text, channel_ts, contact_hint, created_at

contacts
  id, display_name, aliases text[], email, phone, created_at

commitments
  id
  direction        'i_owe' | 'they_owe'
  contact_id       fk
  what             text        -- one sentence, imperative
  due_at           timestamptz null
  due_precision    'exact' | 'day' | 'week' | 'vague' | 'none'
  status           'open' | 'done' | 'dropped' | 'superseded'
  confidence       float
  state            'active' | 'needs_review'
  ambiguity_note   text null   -- human-readable reason it needs review
  created_at, updated_at, last_touch_at
  prompt_version, model

evidence                      -- provenance; many per commitment
  id, commitment_id, source_id, start_char, end_char, quote, is_primary

merges                        -- the dedupe trail
  id, canonical_commitment_id, absorbed_commitment_id,
  reason ('embedding+entity+window'|'manual'|'explicit_restatement'),
  similarity float, created_at

jobs
  id, kind, payload jsonb, status, attempts, error, created_at, finished_at

llm_calls, llm_cache
```

Key invariant: **a commitment is never stored without at least one evidence row.** Enforce
it in the service layer and assert it in a test.

---

## 4. Phases

### Phase 1 — Skeleton and schema
Docker Compose (postgres+pgvector, api, worker, web). FastAPI app with `/health`.
Migrations for every table above. SQLAlchemy models. A seed script that loads 3 sources.
Next.js app that lists sources from the API.

**DoD:** `docker compose up` from clean gives a working web page listing seeded sources.
`pytest` runs (even with two trivial tests). No LLM code yet.

---

### Phase 2 — Extraction with provenance
`POST /sources` (paste or upload text) → creates source, enqueues an `extract` job.
Worker calls OpenAI with a strict schema returning an array of:

```json
{
  "direction": "i_owe",
  "what": "Send the Q3 audience breakdown",
  "who": "Priya Raman",
  "due_raw": "by Friday",
  "confidence": 0.86,
  "quote": "yeah I'll get the Q3 audience numbers over to you before Friday"
}
```

The model returns a **verbatim quote**, not offsets — models are bad at character
counting. Locate the span in Python (exact match, then normalized-whitespace match, then
fuzzy with `rapidfuzz` at ≥90). **If the quote cannot be located in the source, discard
the commitment and log it as a hallucination.** That check is a feature; count it in
evals.

Resolve `due_raw` → `due_at` + `due_precision` in **deterministic Python** using the
source's `channel_ts` as the anchor. "Friday", "next week", "end of month", "in a couple
of days". The LLM never returns a resolved date.

Prompt must explicitly instruct: no inferred promises, politeness is not commitment
("I'll see what I can do", "let's find time sometime" → skip or low confidence),
one commitment per distinct promise.

**DoD:** paste a transcript, see commitments in the DB, each with a locatable span and
a resolved-or-null due date. A test asserts unlocatable quotes are dropped.

---

### Phase 3 — Confidence gating and review queue
Threshold in config (start at 0.75). Below it, or `due_precision` in
(`vague`,`none`) with a deadline implied, or two candidate contacts → `state='needs_review'`
with a written `ambiguity_note`.

The note must be specific and generated as part of the same structured output, e.g.
*"'next week' — relative to this Tuesday call, so Nov 11–15? No specific day given."*
Never "low confidence."

Endpoints: `GET /review`, `POST /commitments/{id}/confirm` (with edited fields),
`POST /commitments/{id}/reject`.

**DoD:** a deliberately ambiguous fixture produces a review item whose note a
non-technical person could act on.

---

### Phase 4 — Dedupe / resolve (the hard part, budget the most time here)
When new commitments are extracted, try to merge each into an existing one. Candidate
gate (cheap, in SQL): same contact (or alias-matched) AND `due_at` within ±4 days or both
null AND created within 30 days. Then score:

- cosine similarity of `what` embeddings (`text-embedding-3-small`) — weight 0.6
- verb/object overlap after lemmatization — weight 0.25
- same direction — hard requirement
- explicit restatement markers ("as discussed", "confirming", "per our call") — +0.15

Bands: ≥0.85 auto-merge · 0.65–0.85 → `needs_review` as a *possible duplicate* with both
quotes shown side by side · <0.65 separate.

On merge: keep the earlier commitment as canonical, **attach the new evidence row to it**
(so one commitment can be provenanced to a call AND an email — this is the money shot of
the demo), take the more precise `due_at`, bump `last_touch_at`, write a `merges` row.

Write the policy down in `NOTES.md` with the reasoning, including what you'd change with
real data. This is the thing you'll be asked about for twenty minutes.

**DoD:** a fixture pair (Tuesday call + Wednesday confirming email about the same
promise) yields exactly one commitment with two evidence rows and a visible merge trail.
A second fixture pair (two *similar but distinct* promises to the same person) stays two
rows. Both are tests.

---

### Phase 5 — Deterministic decay
`api/app/services/decay.py`. Pure functions. No DB, no network, no LLM. Signature roughly:

```python
def decay_score(*, now, due_at, due_precision, last_touch_at,
                direction, status, stated_cadence_days=None) -> DecayResult
```

`DecayResult` carries `score` (0–100), `band` ('fresh'|'warm'|'cooling'|'cold'|'overdue'),
and **`explanation: list[str]`** — the human-readable factors, which the UI renders
verbatim in a tooltip. Something like: *"Promised 9 days ago · due 2 days ago · you owe
them · no contact since the original call."*

Table-driven unit tests. At least 15 cases covering: no due date, overdue, due today,
`they_owe` vs `i_owe` weighting, recently touched, done/dropped short-circuit.

**DoD:** `pytest api/tests/test_decay.py` green, and every branch of the scorer has a
test. State in the README that this is deliberately not LLM-driven, and why.

---

### Phase 6 — Web UI (three screens, no more)
Follow `frontend-design` guidance — restrained, typographic, dense-but-calm. It should
look like a tool an operator uses daily, not a dashboard template. No gradient hero, no
sidebar of empty nav items.

1. **Ledger** — grouped by decay band, each row: what · who · due · band pill · quote
   snippet. Clicking a row opens a **source drawer** with the full artifact and the
   evidence span highlighted; multiple evidence rows show as tabs ("Call · Nov 4",
   "Email · Nov 5"). Merge trail visible here.
2. **Review queue** — one card at a time, ambiguity note prominent, inline edit of
   `what`/`who`/`due`, Confirm / Reject. Duplicate candidates render as a side-by-side
   diff of the two quotes.
3. **Draft composer** — Phase 7's output, editable, with the grounding quotes shown
   beside the draft so the user can see what it's built from.

Plus a small **Ingest** affordance: paste text or pick a fixture from a dropdown. The
dropdown matters — it makes the demo reproducible for someone clicking around for 90
seconds.

**DoD:** a stranger can paste a transcript and reach a drafted follow-up without
instructions.

---

### Phase 7 — Grounded drafts
`POST /commitments/{id}/draft` → retrieves the evidence quotes plus ±400 chars of
surrounding source, and generates a short follow-up (message-length, not email-essay)
that references the specific thing discussed. Tone parameter: `warm` | `direct` |
`brief`. Structured output: `{subject?, body, grounding_quote_ids[]}`.

Prompt constraints: no invented facts, no invented dates, reference the actual artifact,
under 90 words for messages. If the model produces a sentence containing a date not
present in the source or the commitment record, regenerate once, then flag.

**Optional, 30 minutes, worth it:** `POST /webhooks/mock-inbound` that accepts a fake
inbound message, runs the pipeline, and updates the ledger live (SSE or 2s poll). It
communicates the whole "runs on messages" story for almost no cost.

**DoD:** the draft for a fixture commitment quotes something verifiably in the source.

---

### Phase 8 — Eval harness (this is the artifact that gets the interview)
30–40 fixtures in `evals/fixtures/`, hand-labelled, spread across their three stated
segments: a fitness/business coach's session notes, an agency's client call, a
freelancer's WhatsApp thread. Include hard cases on purpose:

- politeness that isn't commitment
- a promise made then explicitly retracted later in the same thread
- third-party commitments ("my designer will send it")
- conditional promises ("if the client approves, I'll...")
- relative dates with an ambiguous anchor
- the same promise across two channels (the dedupe case)
- a thread with **zero** commitments (false-positive check)

Each fixture: `{id}.txt` + `{id}.labels.json` with expected commitments (direction, who,
normalized `what`, expected `due_at` or null) and expected merges.

`evals/run_eval.py` reports, per segment and overall:

- extraction **precision / recall / F1** (match = same direction + contact + date, and
  `what` similarity ≥0.8)
- **hallucinated-deadline rate** (a `due_at` with no textual basis)
- **unlocatable-quote rate** (Phase 2's discard counter)
- **dedupe precision/recall** (correct merges vs over-merges)
- **review-queue precision** — of items sent to review, how many genuinely needed a human
- median latency and cost per source

Write `evals/RESULTS.md` with the numbers **and a failure taxonomy in prose**: the three
categories of mistake, an example of each, and what you'd do about it with real data.
Do not tune the fixtures to make the numbers pretty. Honest 0.82 with a good taxonomy
beats a claimed 0.97.

**DoD:** `python evals/run_eval.py` prints a table, writes RESULTS.md, and the taxonomy
is written in plain English.

---

### Phase 9 — Deploy and package
Cloud Run for api + worker, Cloud SQL, Vercel for web, seeded fixtures in the demo DB, a
"reset demo" endpoint. Rate-limit the ingest endpoint and cap input length — it's a public
link with your OpenAI key behind it.

Then `README.md`, in this order:

1. **What I didn't build and why** — the out-of-scope list from §0, each with one line of
   reasoning. This section is the point of the whole document.
2. What it does — 5 bullets, then the deployed link and the 90-second Loom.
3. The five non-negotiables from §0 and how each is implemented.
4. Eval numbers + link to the failure taxonomy.
5. **The one decision I'd defend hardest** — the dedupe merge policy, or the line between
   LLM and deterministic code. Pick one, argue it, name the tradeoff you accepted.
6. Architecture sketch and how to run locally.

**DoD:** a cold reader who never opens the code understands what was built, what was
deliberately left out, and how well it works.

---

## 5. Working rules for Claude Code

- Commit per phase with a message naming the phase. Small commits inside.
- After each phase, append to `NOTES.md`: what changed, what surprised you, what you
  rejected. This file becomes the README's raw material — do not skip it.
- Tests are not optional in Phases 2, 4, 5, 8. Those four are the technical argument.
- If a phase runs long, cut UI polish, then cut Phase 7's webhook, then cut fixture count
  (floor: 24). **Never** cut the eval harness or the dedupe tests — those are the demo's
  reason to exist.
- Never commit `.env`. Provide `.env.example` with every key documented.
- If something in this plan turns out to be wrong once you're in the code, write down why
  in `NOTES.md` and deviate deliberately. Do not deviate silently.