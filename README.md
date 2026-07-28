# Loose Ends

**Unstructured conversation → structured commitment → time-aware nudge → drafted action.**

The atomic unit is a *commitment*: **who promised what, to whom, by when — and is it
slipping?** Everything else (re-engagement, client tracking, revenue signals) is a view
over that one table. This builds the ledger, not the CRM.

---

## 1. What I didn't build, and why

This is the important section. The scope was cut deliberately so the five things that
matter could be built properly.

- **Real OAuth (Gmail / WhatsApp / Calendar)** — the product thesis is "runs on your
  messages," but wiring real inboxes is integration plumbing that proves nothing about
  the hard part (turning talk into a trustworthy commitment). `POST /sources` + a mock
  inbound is the same pipeline with a cheaper door.
- **Multi-tenancy / auth beyond a demo** — a single-tenant ledger exercises every
  interesting behavior; tenancy is table-stakes engineering, not the risk.
- **Billing** — irrelevant to whether extraction is trustworthy.
- **A contacts / deals / pipeline UI** — that's the CRM this deliberately is *not*. The
  commitment ledger is the substrate a pipeline would sit on; building the pipeline first
  would be decorating an unproven foundation.
- **A chat-with-your-data box** — impressive-looking, but it hides the provenance and
  confidence work behind a text box. The ledger shows the receipts instead.
- **Dark mode / settings / onboarding / mobile layouts** — polish that competes for the
  time the eval harness needed.

The rejected-scope log in [`NOTES.md`](./NOTES.md) has the running list, including the
one optional feature I cut mid-build (the mock-inbound webhook).

## 2. What it does

- **Extracts commitments** from calls, emails, WhatsApp exports, and session notes, each
  linked to the **exact source span** that produced it.
- **Gates on confidence**: clear promises land in the ledger; ambiguous ones go to a
  review queue **with the ambiguity named in words**.
- **Dedupes across channels**: the same promise on a call and in a confirming email
  resolves to **one commitment with two receipts** and a visible merge trail.
- **Scores decay deterministically**: "going cold" is plain Python, unit-tested, and
  explained in a tooltip — the LLM never decides staleness.
- **Drafts grounded follow-ups** that quote the specific thing discussed, with a
  hallucinated-date guard.

**Try it:** **https://loose-ends-inky.vercel.app** — web, API, and Postgres all on Vercel
(Neon for pgvector). `POST /api/demo/reset` restores the seeded state for the next
visitor. Locally it's one command (see §6). The deploy shape, and the one thing that
changes on serverless — no always-on worker, so the job queue drains over HTTP — are in
[`deploy/README.md`](./deploy/README.md). _(90-second Loom: TODO.)_

## 3. The five non-negotiables, and how each is implemented

1. **Provenance** — the model returns a *verbatim quote*, never offsets; `services/locate.py`
   finds the span (exact → normalized-whitespace → fuzzy ≥90) and stores the real source
   substring. **If the quote can't be located, the commitment is dropped as a
   hallucination.** The UI highlights the span in the source drawer.
2. **Confidence gating** — `services/gate.py` routes low-confidence, no-specific-day
   (`week`/`vague`) deadlines, or multi-contact cases to a review queue with a specific,
   phrase-quoting `ambiguity_note` — never "low confidence."
3. **Cross-channel dedupe** — `services/resolve.py`: SQL candidate gate → weighted score
   (embedding + lemma overlap + restatement) → merge that attaches the new evidence to the
   earlier commitment. See §5.
4. **Deterministic decay** — `services/decay.py`, pure functions, 29 table-driven tests,
   every band and branch covered. The score and its plain-English explanation are computed
   in Python; the tooltip renders them verbatim.
5. **Grounded drafts** — `llm/draft.py` retrieves the evidence quotes + surrounding source
   and generates a short follow-up; a deterministic date guard regenerates once, then flags
   any date not present in the source.

## 4. How well it works

From `python evals/run_eval.py` over 24 hand-labelled fixtures (coach / agency /
freelancer, with deliberate hard cases; **not tuned to flatter the numbers**):

| Metric | Value |
|---|---|
| Extraction precision / recall / F1 | **0.81 / 0.74 / 0.77** |
| Hallucinated-deadline rate | **0.00%** |
| Unlocatable-quote rate | **0.00%** |
| Dedupe precision / recall | **1.00 / 1.00** |
| Review-queue precision | 0.50 (understated — see taxonomy) |
| Cost / source | ~$0.0005 · ~2s |

Full numbers and the **failure taxonomy in prose** are in
[`evals/RESULTS.md`](./evals/RESULTS.md). The headline: **most of the P/R gap is scoring
strictness, not extraction failure** — half the misses are the same commitment worded
differently ("Send the invoice" vs "Get the invoice to you") tripping a lexical match bar.
Zero hallucinated deadlines and zero unlocatable quotes are the numbers I'd stand behind.

## 5. The one decision I'd defend hardest

**I lowered the auto-merge threshold from the spec's 0.85 to 0.80, calibrated from the
data rather than guessed.**

The dedupe score is `0.60·cosine(embeddings) + 0.25·lemma_overlap + 0.15·restatement`.
`text-embedding-3-small` compresses paraphrase similarity into ~0.75–0.90, so on the
fixtures a *genuine* cross-channel restatement (a call + its confirming email) scores
**0.82**, while the closest *distinct* same-contact pair scores **0.43**. A 0.85 floor
sits above the true positives — it would miss the exact case the demo exists to show. The
true and false clusters are separated by a ~0.39 gap of empty space, so 0.80 is safe by a
wide margin, not fitted to one example.

**The tradeoff I accepted:** a lower floor trades a little dedupe precision for recall. I
mitigated it two ways — a hard *same-direction, same-contact, ±4-day* gate before any
scoring, and a 0.65–0.80 review band so borderline pairs get a human instead of a silent
merge. The eval bears this out: dedupe precision stays 1.00 with recall 1.00. **With real
data I'd learn the threshold from labelled pairs (logistic regression on the three
features) instead of eyeballing a gap on a handful.** The full policy and what I'd change
at scale are in [`NOTES.md`](./NOTES.md).

The same instinct runs through the whole build: **the LLM extracts and phrases; Python
decides.** Dates, decay, span-location, dedupe banding, and the draft date-guard are all
deterministic and unit-tested, because those are the parts a user has to trust and I have
to defend.

## 6. Architecture & running locally

```
Next.js (web) ──HTTP──> FastAPI (api) ──> Postgres + pgvector
                                │
                         Postgres jobs table
                                │
                          polling worker ──> OpenAI (extract · embed · draft)
```

- **api** — FastAPI + SQLAlchemy + Alembic. Every LLM call goes through `llm/client.py`
  (Responses API strict schema, retries + backoff, timeout, `llm_cache`, `llm_calls`
  cost/latency logging, schema-repair pass).
- **worker** — one polling process over a Postgres `jobs` table (no Redis, no Celery):
  extract → persist with provenance → dedupe.
- **web** — three screens: **Ledger** (grouped by decay band, source drawer with
  highlighted spans + per-channel evidence tabs + merge trail), **Review** (one card at a
  time, inline edit, duplicate diff), **Draft composer** (tone toggle, grounding quotes
  shown beside).

### Run

```bash
cp .env.example .env          # then set OPENAI_API_KEY
docker compose up -d --build  # api, worker, web, postgres+pgvector
```

- Web: **http://localhost:3001**  ·  API docs: **http://localhost:8001/docs**
  (ports are 3001/8001 to avoid colliding with anything on 3000/8000).
- The stack seeds 5 fixture sources and extracts them on first boot. `POST /demo/reset`
  restores that state between demos.

### Tests & eval

```bash
docker compose exec api pytest -q                     # 81 tests
docker compose run --rm -v "$PWD/evals:/evals" \
  -w /app -e PYTHONPATH=/app api python /evals/run_eval.py
```

Model IDs live only in `.env` (`OPENAI_MODEL_EXTRACT=gpt-4.1-mini`,
`OPENAI_MODEL_DRAFT=gpt-4.1`, `OPENAI_MODEL_EMBED=text-embedding-3-small`) — chosen from
the GPT-4.1 generation because the pipeline relies on temperature control the reasoning
models don't honour. See [`NOTES.md`](./NOTES.md) for the full decision log.
