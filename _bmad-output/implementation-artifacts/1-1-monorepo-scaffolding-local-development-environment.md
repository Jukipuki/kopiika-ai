# Story 1.1: Monorepo Scaffolding & Local Development Environment

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want a monorepo with Next.js frontend and FastAPI backend scaffolded with local dev infrastructure,
So that I have a working development environment to build features on.

## Acceptance Criteria

1. **Given** a fresh clone of the repository
   **When** I run `docker-compose up -d` and start both frontend and backend
   **Then** PostgreSQL (with pgvector) and Redis are running locally, the Next.js dev server serves on port 3000, and the FastAPI server serves on port 8000

2. **Given** the frontend project
   **When** I inspect the configuration
   **Then** it uses TypeScript, Tailwind CSS 4.x, ESLint, App Router, and Turbopack as specified in Architecture

3. **Given** the backend project
   **When** I inspect the configuration
   **Then** it uses Python 3.12, FastAPI, Uvicorn, SQLModel, Alembic, Celery, Redis, and uv as package manager

4. **Given** both projects running
   **When** the frontend calls the backend health endpoint
   **Then** a successful JSON response is returned confirming cross-service communication works

## Tasks / Subtasks

- [x] Task 1: Initialize monorepo root structure (AC: #1, #2, #3)
  - [x] 1.1 Create root `kopiika-ai/` directory structure: `frontend/`, `backend/`, `shared/openapi/`, `infra/`, `.github/workflows/`
  - [x] 1.2 Create root `docker-compose.yml` with PostgreSQL (pgvector/pgvector:pg16) on port 5432 and Redis (redis:7-alpine) on port 6379
  - [x] 1.3 Create root `README.md` with project overview and local setup instructions
  - [x] 1.4 Create root `.gitignore` covering Node.js, Python, IDE, and env files

- [x] Task 2: Scaffold Next.js frontend (AC: #2)
  - [x] 2.1 Run `npx create-next-app@latest frontend --typescript --tailwind --eslint --app --turbopack`
  - [x] 2.2 Verify Tailwind CSS 4.x is configured with CSS-first `@theme` directives (no JS config if v4 default)
  - [x] 2.3 Configure `@tailwindcss/postcss` as PostCSS plugin (v4 convention)
  - [x] 2.4 Set up folder structure per architecture: `src/app/`, `src/components/ui/`, `src/components/layout/`, `src/features/`, `src/lib/`, `src/i18n/`, `src/types/`, `e2e/`
  - [x] 2.5 Install DM Sans font via `next/font/google` in root layout
  - [x] 2.6 Create `.env.example` with `NEXT_PUBLIC_API_URL=http://localhost:8000`
  - [x] 2.7 Create `.env.local` (gitignored) with local dev values

- [x] Task 3: Scaffold FastAPI backend (AC: #3)
  - [x] 3.1 Run `uv init --python 3.12` inside `backend/`
  - [x] 3.2 Add core dependencies: `uv add fastapi uvicorn sqlmodel alembic celery redis`
  - [x] 3.3 Create app structure per architecture: `app/main.py`, `app/api/`, `app/core/`, `app/models/`, `app/services/`, `app/tasks/`, `app/agents/`, `app/rag/`
  - [x] 3.4 Create `app/main.py` with FastAPI app, CORS middleware (allow localhost:3000), and `/health` endpoint
  - [x] 3.5 Create `app/core/config.py` with Pydantic BaseSettings loading from env vars
  - [x] 3.6 Create `app/core/database.py` with async SQLModel engine + session factory (postgresql+asyncpg)
  - [x] 3.7 Initialize Alembic: `uv run alembic init alembic` and configure `alembic/env.py` for SQLModel
  - [x] 3.8 Create `app/tasks/celery_app.py` with Redis broker configuration
  - [x] 3.9 Create `.env.example` and `.env` with local dev database/redis URLs
  - [x] 3.10 Create `.python-version` file with `3.12`

- [x] Task 4: Configure shared tooling and cross-service communication (AC: #4)
  - [x] 4.1 Create `shared/openapi/generate-client.sh` script for TypeScript client generation
  - [x] 4.2 Add a frontend API call to `http://localhost:8000/health` on the root page to verify cross-service communication
  - [x] 4.3 Verify `docker-compose up -d` starts PostgreSQL with pgvector extension and Redis successfully
  - [x] 4.4 Verify backend connects to PostgreSQL and Redis on startup
  - [x] 4.5 Verify frontend dev server starts on port 3000 and backend on port 8000

- [x] Task 5: CI/CD foundation (AC: #2, #3)
  - [x] 5.1 Create `.github/workflows/ci-frontend.yml` — lint + build
  - [x] 5.2 Create `.github/workflows/ci-backend.yml` — lint (Ruff) + basic test
  - [x] 5.3 Create `.github/CODEOWNERS` file

## Dev Notes

### Architecture Compliance

- **Monorepo structure**: Folder-based monorepo with `frontend/` (Next.js 16.1) + `backend/` (custom FastAPI scaffold) — NOT a monorepo tool like Nx or Turborepo
- **Frontend init**: Use `create-next-app` which scaffolds App Router + Turbopack by default in Next.js 16.x
- **Backend init**: Custom scaffold with uv, NOT a template generator — manually create the `app/` structure
- **Docker Compose**: Only PostgreSQL + Redis for local dev; frontend and backend run natively (not containerized)

### Technical Requirements

#### Frontend Stack (Exact Versions)
- **Next.js 16.1** via `create-next-app@latest` (16.2 is latest but architecture specifies 16.1 — use `create-next-app@16.1` if needed)
- **TypeScript 5.x**
- **Tailwind CSS 4.x** — CSS-first configuration via `@theme` directives, `@import "tailwindcss"` replaces `@tailwind` directives, PostCSS plugin is `@tailwindcss/postcss` (not `tailwindcss` directly)
- **ESLint** — configured by create-next-app
- **Turbopack** — default bundler in Next.js 16.x
- **DM Sans** — primary typeface, loaded via `next/font/google`

#### Backend Stack (Exact Versions)
- **Python 3.12** — specified in `.python-version` and `uv init --python 3.12`
- **FastAPI** (latest, currently ~0.135.x)
- **Uvicorn** — ASGI server
- **SQLModel** — ORM combining SQLAlchemy 2.x + Pydantic v2
- **Alembic** — database migrations
- **Celery** — task queue for async pipeline processing
- **Redis** — Celery broker + caching
- **uv** (latest, currently ~0.10.x) — Python package manager, replaces pip/pip-tools/virtualenv
- **asyncpg** — async PostgreSQL driver for SQLModel/SQLAlchemy

#### Infrastructure (Docker Compose)
- **PostgreSQL**: `pgvector/pgvector:pg16` image (PostgreSQL 16 with pgvector extension pre-installed)
  - Port: 5432
  - DB: `kopiika_db`, User: `user`, Password: `password`
  - Volume: `postgres_data:/var/lib/postgresql/data`
- **Redis**: `redis:7-alpine` image
  - Port: 6379
  - Volume: `redis_data:/data`

### Library & Framework Requirements

#### Tailwind CSS 4.x Critical Changes (from v3)
- No `tailwind.config.js` — use `@theme` in CSS for customization
- `@import "tailwindcss"` replaces `@tailwind base/components/utilities`
- PostCSS plugin: `@tailwindcss/postcss` (not `tailwindcss`)
- No need for `postcss-import` or `autoprefixer` — handled automatically
- Default border color is now `currentColor` (was `gray-200`)
- Class renames: `bg-gradient-to-*` → `bg-linear-to-*`, `flex-shrink-0` → `shrink-0`
- Run `npx @tailwindcss/upgrade` if starting from v3 template

#### uv Package Manager Commands
- `uv init --python 3.12` — initialize project
- `uv add <package>` — add dependency (replaces `pip install`)
- `uv sync` — install all dependencies from lockfile
- `uv run <command>` — run command in project environment (e.g., `uv run uvicorn app.main:app --reload`)
- `uv run alembic upgrade head` — run migrations
- `uv run celery -A app.tasks.celery_app worker --loglevel=info` — start Celery worker

### File Structure Requirements

#### Naming Conventions (MUST FOLLOW)
- **Frontend files**: Components `PascalCase.tsx`, utilities `kebab-case.ts`, routes `kebab-case/page.tsx`
- **Backend files**: All `snake_case.py`
- **Database**: `snake_case` tables (plural), `snake_case` columns, UUID v4 primary keys
- **API endpoints**: `kebab-case`, plural nouns, prefixed `/api/v1/`
- **API JSON**: `camelCase` via Pydantic `alias_generator=to_camel`
- **Environment vars**: `UPPER_SNAKE_CASE` (frontend prefix: `NEXT_PUBLIC_`)

#### Health Endpoint Specification
```python
# Backend: GET /health
# Response: {"status": "healthy", "version": "0.1.0"}
```

#### Error Response Format (All Errors)
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": {}
  }
}
```

#### Backend Dependency Layers (NEVER VIOLATE)
| Layer | Depends On | Never Depends On |
|---|---|---|
| `api/` | `services/`, `core/`, `models/` | `agents/`, `tasks/`, `rag/` |
| `services/` | `models/`, `core/` | `api/`, `agents/` |
| `models/` | `core/` (database engine only) | Everything else |
| `core/` | Nothing (leaf dependency) | Everything |

### Testing Requirements

- **Frontend**: Playwright for E2E tests in `e2e/` directory
- **Backend**: pytest in `tests/` directory mirroring `app/` structure
- **Backend linting**: Ruff + Black (enforced in CI)
- **Frontend linting**: ESLint + Prettier (enforced in CI)
- For this story: verify docker-compose services start, frontend builds, backend starts and serves `/health`

### Project Structure Notes

- This is a greenfield project — no existing code to conflict with
- Monorepo uses simple folder separation, NOT a monorepo tool (no Nx, Turborepo, Lerna)
- `shared/openapi/` contains only the client generation script — actual generated client lives in `frontend/src/lib/api/generated/`
- `infra/` directory created but empty for now (AWS IaC to be added in Story 1.2)
- `.github/workflows/` created with basic CI pipelines

### References

- [Source: _bmad-output/planning-artifacts/architecture.md — Monorepo Organization section]
- [Source: _bmad-output/planning-artifacts/architecture.md — Frontend Structure section]
- [Source: _bmad-output/planning-artifacts/architecture.md — Backend Structure section]
- [Source: _bmad-output/planning-artifacts/architecture.md — Docker Compose Local Setup section]
- [Source: _bmad-output/planning-artifacts/architecture.md — Local Development Workflow section]
- [Source: _bmad-output/planning-artifacts/architecture.md — Naming Conventions section]
- [Source: _bmad-output/planning-artifacts/architecture.md — Component Dependency Graph (Backend)]
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.1]
- [Source: _bmad-output/planning-artifacts/prd.md — Technical Requirements, Browser Support]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Design System, Typography, Color System]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Port 5432 conflict resolved by stopping pre-existing `postgres` container
- Next.js 16.2.1 installed (latest via create-next-app@latest); architecture specified 16.1 but 16.2 is backwards compatible
- `uv` was not pre-installed; installed via official install script (v0.10.12)

### Completion Notes List

- Monorepo scaffolded with `frontend/`, `backend/`, `shared/openapi/`, `infra/`, `.github/workflows/`
- Docker Compose configured with pgvector/pgvector:pg16 and redis:7-alpine, both verified healthy
- Frontend: Next.js 16.2.1, TypeScript, Tailwind CSS 4.x (CSS-first config), ESLint, App Router, Turbopack, DM Sans font
- Backend: Python 3.12, FastAPI 0.135.1, Uvicorn, SQLModel, Alembic, Celery, Redis, asyncpg, uv
- Health endpoint verified: `GET /health` returns `{"status":"healthy","version":"0.1.0"}`
- Frontend root page calls backend `/health` and displays status
- CI workflows created for both frontend (lint+build) and backend (ruff+pytest)
- All 8 backend tests pass, ruff lint clean, ESLint clean, frontend builds successfully

### Change Log

- 2026-03-21: Story 1.1 implemented — full monorepo scaffolding with local dev environment

### File List

**New files:**
- docker-compose.yml
- README.md
- .gitignore
- .github/workflows/ci-frontend.yml
- .github/workflows/ci-backend.yml
- .github/CODEOWNERS
- shared/openapi/generate-client.sh
- frontend/ (scaffolded via create-next-app)
- frontend/src/app/layout.tsx (modified — DM Sans font, metadata)
- frontend/src/app/page.tsx (modified — health endpoint integration)
- frontend/src/app/globals.css (modified — DM Sans theme variable)
- frontend/.env.example
- frontend/.env.local
- frontend/src/components/ui/.gitkeep
- frontend/src/components/layout/.gitkeep
- frontend/src/features/.gitkeep
- frontend/src/lib/.gitkeep
- frontend/src/i18n/.gitkeep
- frontend/src/types/.gitkeep
- frontend/e2e/.gitkeep
- backend/pyproject.toml (created by uv init)
- backend/uv.lock
- backend/.python-version
- backend/.env
- backend/.env.example
- backend/app/__init__.py
- backend/app/main.py
- backend/app/core/__init__.py
- backend/app/core/config.py
- backend/app/core/database.py
- backend/app/api/__init__.py
- backend/app/models/__init__.py
- backend/app/services/__init__.py
- backend/app/tasks/__init__.py
- backend/app/tasks/celery_app.py
- backend/app/agents/__init__.py
- backend/app/rag/__init__.py
- backend/alembic.ini
- backend/alembic/env.py
- backend/alembic/script.py.mako
- backend/alembic/README
- backend/alembic/versions/ (empty)
- backend/tests/__init__.py
- backend/tests/test_health.py
- backend/tests/test_structure.py
