# Kopiika AI

AI-powered personal finance education platform that transforms bank statements into personalized financial literacy lessons.

## Project Structure

```
kopiika-ai/
├── frontend/          # Next.js 16.1 (TypeScript, Tailwind CSS 4.x)
├── backend/           # FastAPI (Python 3.12, SQLModel, Celery)
├── shared/openapi/    # OpenAPI client generation scripts
├── infra/             # AWS infrastructure (IaC)
├── .github/workflows/ # CI/CD pipelines
└── docker-compose.yml # Local dev infrastructure
```

## Prerequisites

- Node.js 20+
- Python 3.12
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker & Docker Compose

## Local Setup

### 1. Start infrastructure services

```bash
docker-compose up -d
```

This starts:
- **PostgreSQL** (pgvector/pgvector:pg16) on port 5432
- **Redis** (redis:7-alpine) on port 6379

### 2. Configure environment variables

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env` and fill in the required values:

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://user:password@localhost:5432/kopiika_db` | Matches docker-compose defaults |
| `REDIS_URL` | `redis://localhost:6379/0` | Matches docker-compose defaults |
| `COGNITO_USER_POOL_ID` | — | AWS Cognito User Pool ID |
| `COGNITO_APP_CLIENT_ID` | — | Cognito frontend client ID |
| `S3_BUCKET_NAME` | `kopiika-uploads-dev` | S3 bucket for file uploads |
| `OPENAI_API_KEY` | — | Required for RAG embeddings (text-embedding-3-small) |
| `ANTHROPIC_API_KEY` | — | Required for AI agents (Claude) |

The database and Redis URLs work out of the box with the docker-compose defaults.

### 3. Backend setup

```bash
cd backend
uv sync
```

### 4. Run database migrations

```bash
cd backend
uv run alembic upgrade head
```

This creates all required tables including `document_embeddings` (pgvector) for RAG.

### 5. Seed RAG knowledge base

Populate the vector embeddings used for financial literacy content retrieval:

```bash
cd backend
uv run python -m app.rag.seed
```

This reads markdown documents from `backend/data/rag-corpus/{en,uk}/`, chunks them by H2 sections, embeds via OpenAI `text-embedding-3-small`, and upserts into the `document_embeddings` table. The command is idempotent — safe to re-run.

Requires `OPENAI_API_KEY` to be set in `.env`.

### 6. Start the backend API

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

### 7. Start the Celery worker (separate terminal)

Celery processes async tasks like bank statement parsing, transaction categorization, and insight generation:

```bash
cd backend
uv run celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
```

There is no Celery Beat schedule — all tasks are event-driven (triggered by API calls).

### 8. Start the frontend (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

### 9. Verify setup

- Backend health: http://localhost:8000/health
- Frontend: http://localhost:3000

## Development

- **Frontend linting:** `cd frontend && npm run lint`
- **Backend linting:** `cd backend && uv run ruff check .`
- **Run tests:** `cd backend && uv run pytest`
- **Run migrations:** `cd backend && uv run alembic upgrade head`
- **Create migration:** `cd backend && uv run alembic revision --autogenerate -m "description"`
- **Rollback migration:** `cd backend && uv run alembic downgrade -1`
- **Start Celery worker:** `cd backend && uv run celery -A app.tasks.celery_app worker --loglevel=info`
- **Re-seed RAG corpus:** `cd backend && uv run python -m app.rag.seed`
