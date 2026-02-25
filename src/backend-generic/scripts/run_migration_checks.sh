#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  export DATABASE_URL="postgresql+psycopg://prodgrade:prodgrade@localhost:5432/prodgrade"
fi

echo "[migrations] Running alembic upgrade head"
alembic upgrade head

echo "[migrations] Running migration validation checks"
python3 scripts/test_migrations.py

echo "[migrations] All migration checks passed."

