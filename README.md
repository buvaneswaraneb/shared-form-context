# Shared Prompt Context Service

Small FastAPI service for storing deduplicated prompt context. It hashes normalized prompts with SHA-256 and does no AI processing, embeddings, vector search, or RAG.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

By default, local development uses `./prompts.db`. For Vercel, set `DATABASE_URL` to a hosted PostgreSQL connection string such as a free Neon database. The Vercel cron invokes `/internal/process`; set `CRON_SECRET` when using an external scheduler or when protecting that endpoint.

## API

- `POST /send` with `{ "prompt": "..." }`; returns the deterministic hash ID and whether it already existed.
- `GET /query?limit=50&offset=0`; returns newest prompts first.
- `GET /today`; returns prompts created since UTC midnight.
- `GET` or `POST /internal/process`; processes a batch of pending records (used by Vercel Cron).
- `GET /health`.

The in-process scheduler is enabled by default for long-running deployments. On Vercel, serverless instances are short-lived, so the configured cron endpoint is the durable scheduling mechanism; set `SCHEDULER_ENABLED=false` there if desired.
