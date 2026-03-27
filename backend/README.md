1. Infrastructure (Postgres + Redis)

docker-compose up -d
2. Backend (FastAPI on :8000)

cd backend
cp .env.example .env          # fill in Cognito credentials
uv sync                       # install dependencies
.venv/bin/alembic upgrade head # run migrations
.venv/bin/uvicorn app.main:app --reload
3. Frontend (Next.js on :3000)

cd frontend
cp .env.example .env.local    # fill in Cognito + NEXTAUTH_SECRET
npm install
npm run dev
Quick checks
Backend health: http://localhost:8000/health
Frontend: http://localhost:3000