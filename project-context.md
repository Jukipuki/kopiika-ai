# Project Context

Conventions and rules every dev agent must follow in this repo. Loaded automatically by `dev-story` and `quick-dev` workflows.

---

## Versioning

**Policy doc:** [`docs/versioning.md`](docs/versioning.md)  
**Source of truth:** [`/VERSION`](VERSION) — one line, no leading `v`, one trailing newline.

### Bump rules

| Change type | Digit to bump | Example |
|---|---|---|
| New user-facing feature or behaviour | MINOR | `1.4.0` → `1.5.0` |
| Bug-fix or polish-only, no new functionality | PATCH | `1.5.0` → `1.5.1` |
| Phase boundary | MAJOR | `1.x.x` → `2.0.0` (confirm with user first) |

### When to bump

**Every story or fix that is committed gets a version bump — no exceptions.**  
The bump happens as the final step before marking work ready for review, in the same commit/PR as the code change.

Steps:
1. Read the current `/VERSION`
2. Determine MINOR vs PATCH (see table above)
3. Write the new version to `/VERSION` — one line, no leading `v`, one trailing newline
4. Include `/VERSION` in the file list / changed-files summary

---

## Tech-Debt Register

Log at [`docs/tech-debt.md`](docs/tech-debt.md). Reference entries by ID (`TD-001`, etc.) in PRs and code comments. Use `TD-NNN` format for new entries — pick the next unused number.

---

## Test Commands

```bash
# Backend (run from repo root or backend/)
cd backend && source .venv/bin/activate && python -m pytest

# Frontend (run from frontend/)
cd frontend && npm test -- --run
```

Backend venv lives at `backend/.venv` (not repo root).

**Backend lint is a CI gate.** After any backend change, run `ruff check` (and `ruff check --fix` for autofixable issues) alongside the tests — CI runs ruff and will fail the PR otherwise. Do not commit backend code without a clean ruff pass.

```bash
cd backend && source .venv/bin/activate && ruff check
```

---

## Project Structure

```
kopiika-ai/
├── backend/          FastAPI + Celery + LangGraph (Python)
├── frontend/         Next.js 15 + TypeScript
├── docs/             Policy and reference docs (versioning.md, tech-debt.md, …)
├── VERSION           Single source-of-truth version string
└── _bmad/            BMAD planning and workflow tooling (do not modify during stories)
```

Monorepo with two separate stacks — backend and frontend are independent services.
