# AI-Powered Code Review Assistant

Backend service that automates code reviews. A FastAPI surface sits on top of a
CodeBERT pipeline plus static-analysis rules, with PostgreSQL for state and
Redis for hot-path caching. Flags bugs, security issues, and anti-patterns in
real time. A thin React dashboard runs on top.

## Architecture

```
                ┌────────────────────────┐
                │   React Dashboard       │
                │   (Vite, on :5173)      │
                └────────────┬────────────┘
                             │ REST
                             ▼
              ┌─────────────────────────────┐
              │     FastAPI (:8000)         │
              │  ┌───────────────────────┐  │
              │  │   Review Service      │  │
              │  │  ┌─────────┐ ┌──────┐ │  │
              │  │  │CodeBERT │ │Rules │ │  │
              │  │  │pipeline │ │engine│ │  │
              │  │  └─────────┘ └──────┘ │  │
              │  └──────────┬────────────┘  │
              └─────────────┼───────────────┘
                  ┌─────────┼─────────┐
                  ▼                   ▼
            ┌──────────┐        ┌─────────┐
            │PostgreSQL│        │  Redis  │
            │ (state)  │        │ (cache) │
            └──────────┘        └─────────┘
```

## Detection

Each submitted snippet is scored along three tracks:

1. **Rule engine** — regex/AST checks for known security issues
   (eval/exec, `shell=True`, hardcoded secrets, SQL string-formatting,
   weak hashing), correctness bugs (mutable default args, bare `except`,
   `==` against `None`), and anti-patterns (god functions, deep nesting,
   wildcard imports).
2. **CodeBERT embeddings** — `microsoft/codebert-base` encodes the
   snippet. Cosine similarity against a curated set of "anti-pattern
   exemplars" produces a learned-signal score that catches patterns the
   rules miss.
3. **Composite severity** — rule hits and embedding scores are merged
   into a single `info | warning | error | critical` rating per finding.

Identical snippets hit Redis and skip the model. Results are persisted to
Postgres for history and aggregate metrics.

## Stack

- **Backend:** FastAPI · SQLAlchemy 2 · Pydantic v2 · transformers · torch
- **Storage:** PostgreSQL 16 · Redis 7
- **Frontend:** React 18 · Vite · Monaco editor
- **Infra:** Docker Compose, single command up

## Quickstart

```bash
# 1. Start Postgres + Redis + backend + frontend
docker compose up --build

# 2. Open the dashboard
open http://localhost:5173

# 3. Backend API docs
open http://localhost:8000/docs
```

First boot pulls `microsoft/codebert-base` (~500MB) into a cached volume; the
service stays responsive because the model loads lazily on first review.

### Local dev (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/codereview
export REDIS_URL=redis://localhost:6379/0
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## API

| Method | Path                    | Description                               |
| ------ | ----------------------- | ----------------------------------------- |
| POST   | `/api/reviews`          | Submit code for review                    |
| GET    | `/api/reviews`          | List recent reviews (paginated)           |
| GET    | `/api/reviews/{id}`     | Fetch one review with findings            |
| GET    | `/api/reviews/stats`    | Aggregate counts by severity / category   |
| GET    | `/healthz`              | Liveness                                  |
| GET    | `/readyz`               | Readiness (checks DB + Redis)             |

### Submit a review

```bash
curl -X POST http://localhost:8000/api/reviews \
  -H 'Content-Type: application/json' \
  -d '{
    "language": "python",
    "code": "def login(user, pw):\n  query = \"SELECT * FROM u WHERE name=\" + user\n  return db.exec(query)"
  }'
```

Response:

```json
{
  "id": "0b3f...",
  "language": "python",
  "summary": {"critical": 1, "error": 0, "warning": 1, "info": 0},
  "findings": [
    {
      "category": "security",
      "severity": "critical",
      "rule_id": "PY-SEC-001",
      "line": 2,
      "message": "Possible SQL injection: string-concatenated query",
      "suggestion": "Use parameterised queries (e.g., db.execute(sql, (user,)))"
    },
    {
      "category": "anti-pattern",
      "severity": "warning",
      "rule_id": "ML-SIM-014",
      "line": null,
      "message": "Snippet resembles a known anti-pattern (similarity 0.83)",
      "suggestion": "Compare against canonical secure-auth example"
    }
  ],
  "cached": false,
  "latency_ms": 142
}
```

## Project layout

```
backend/
  app/
    main.py              # FastAPI app, middleware, lifespan
    config.py            # Pydantic settings
    database.py          # SQLAlchemy engine / session
    cache.py             # Async Redis client
    models.py            # ORM models
    schemas.py           # Pydantic request/response models
    ml/
      analyzer.py        # CodeBERT pipeline + composite scorer
      rules.py           # Rule registry (regex + AST checks)
      exemplars.py       # Anti-pattern reference snippets
    routers/
      reviews.py
      health.py
    services/
      review_service.py  # Orchestrates cache + rules + ML + persistence
  tests/
  requirements.txt
  Dockerfile

frontend/
  src/
    App.jsx
    api.js
    components/
      CodeEditor.jsx
      ReviewResults.jsx
      ReviewHistory.jsx
      StatsPanel.jsx
  package.json
  Dockerfile
```

## Running the tests

```bash
cd backend
pytest -q
```

## License

MIT
