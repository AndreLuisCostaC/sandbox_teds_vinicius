# Prodgrade Monorepo

Monorepo bootstrap for:
- Store frontend (`Next.js`) on `http://localhost:3000`
- ERP frontend (`Next.js`) on `http://localhost:3001`
- Backend API (`FastAPI`) on `http://localhost:8000`
- PostgreSQL on `localhost:5432`
- ChromaDB on `http://localhost:8001`

## Prerequisites

- Docker
- Docker Compose (v2)

## Quick Start

1. Create your local environment file:

```bash
cp .env.example .env
```

2. Start the full stack:

```bash
docker compose up -d
```

3. Check service status:

```bash
docker compose ps
```

## Smoke Test

Run the smoke test script to validate:
- All services are healthy
- Frontend and backend HTTP endpoints respond
- PostgreSQL accepts connections
- ChromaDB heartbeat endpoint responds

```bash
./scripts/test-smoke.sh
```

## Useful Commands

Stop services:

```bash
docker compose down
```

Stop services and remove volumes:

```bash
docker compose down -v
```

View logs:

```bash
docker compose logs -f
```

## Load and Security Validation

Run end-to-end load tests (search, orders, ERP dashboard APIs):

```bash
./scripts/run-load-tests.sh
```

Run security-oriented checks (Bandit + npm audit):

```bash
./scripts/run-security-scans.sh
```

Both commands write timestamped reports under `reports/`.
