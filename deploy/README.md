# Deploy runbook

The whole system runs locally with `docker compose up` (see the root README). This
directory is the path to a public demo: **API + worker on Cloud Run, Postgres on Cloud
SQL, web on Vercel.**

> **Prereqs you must provide** (I can't do these without your credentials): a GCP project
> with billing, `gcloud` installed + `gcloud auth login`, and `vercel login`. Set
> `PROJECT_ID`, `REGION` (e.g. `us-central1`) below.

## 1. Postgres — Cloud SQL (with pgvector)

```bash
gcloud sql instances create looseends-db \
  --database-version=POSTGRES_15 --tier=db-f1-micro --region="$REGION"
gcloud sql databases create looseends --instance=looseends-db
gcloud sql users set-password loose --instance=looseends-db --password="$DB_PASSWORD"
# enable pgvector once, via the connected psql:
#   CREATE EXTENSION IF NOT EXISTS vector;   (migration 0001 also does this)
```

Connection string (Cloud Run uses the Cloud SQL socket):
`postgresql+psycopg://loose:$DB_PASSWORD@/looseends?host=/cloudsql/$PROJECT_ID:$REGION:looseends-db`

## 2. API + worker — Cloud Run (one image, two services)

Both run the **same image** (`api/Dockerfile`) with different start commands.

```bash
# build + push
gcloud builds submit ./api --tag "gcr.io/$PROJECT_ID/looseends-api"

# API service — runs migrations then serves on $PORT
gcloud run deploy looseends-api \
  --image "gcr.io/$PROJECT_ID/looseends-api" \
  --region "$REGION" --allow-unauthenticated \
  --add-cloudsql-instances "$PROJECT_ID:$REGION:looseends-db" \
  --set-env-vars "DATABASE_URL=postgresql+psycopg://loose:$DB_PASSWORD@/looseends?host=/cloudsql/$PROJECT_ID:$REGION:looseends-db" \
  --set-env-vars "OPENAI_API_KEY=$OPENAI_API_KEY,OPENAI_MODEL_EXTRACT=gpt-4.1-mini,OPENAI_MODEL_DRAFT=gpt-4.1,OPENAI_MODEL_EMBED=text-embedding-3-small" \
  --command sh --args "-c","alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port \$PORT"

# Worker service — no HTTP; keep 1 instance always warm (it's a poller)
gcloud run deploy looseends-worker \
  --image "gcr.io/$PROJECT_ID/looseends-api" \
  --region "$REGION" --no-cpu-throttling --min-instances 1 --max-instances 1 \
  --add-cloudsql-instances "$PROJECT_ID:$REGION:looseends-db" \
  --set-env-vars "DATABASE_URL=...,OPENAI_API_KEY=...,OPENAI_MODEL_EXTRACT=gpt-4.1-mini,OPENAI_MODEL_DRAFT=gpt-4.1,OPENAI_MODEL_EMBED=text-embedding-3-small" \
  --command python --args "-m","app.worker"
```

Note the API service is public with a real OpenAI key behind it — the ingest endpoint is
already rate-limited (`INGEST_RATE_LIMIT_PER_MIN`) and input-capped (`MAX_INPUT_CHARS`).
Set both via `--set-env-vars` to taste.

## 3. Web — Vercel

```bash
cd web
vercel link
vercel env add NEXT_PUBLIC_API_BASE production   # -> https://looseends-api-...run.app
vercel env add API_BASE_INTERNAL production       # same public URL (Vercel has no VPC to Cloud Run)
vercel --prod
```

## 4. Reset between demos

`POST https://looseends-api-...run.app/demo/reset` wipes extracted data, re-seeds the
fixtures, and re-enqueues extraction — so a shared link is reproducible for the next
visitor.

## What I would harden before real traffic

- Rate limiting is per-instance (in-memory). Multi-instance needs Redis or a Postgres
  counter.
- Secrets via Secret Manager, not `--set-env-vars`.
- Migrations as a dedicated Cloud Run Job (or `gcloud builds` step) instead of on API
  boot, to avoid a cold-start race if the API scales to >1 instance.
