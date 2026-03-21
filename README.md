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
- **PostgreSQL** (with pgvector) on port 5432
- **Redis** on port 6379

### 2. Start the backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:3000, backend on http://localhost:8000.

### 4. Verify setup

- Backend health: http://localhost:8000/health
- Frontend: http://localhost:3000

## Development

- **Frontend linting:** `cd frontend && npm run lint`
- **Backend linting:** `cd backend && uv run ruff check .`
- **Run migrations:** `cd backend && uv run alembic upgrade head`
- **Start Celery worker:** `cd backend && uv run celery -A app.tasks.celery_app worker --loglevel=info`
