#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    echo "[smoke] .env not found. Creating from .env.example"
    cp .env.example .env
  else
    echo "[smoke] ERROR: neither .env nor .env.example exists."
    exit 1
  fi
fi

echo "[smoke] Starting stack with docker compose"
docker compose up -d

wait_for_health() {
  local service="$1"
  local timeout_seconds="${2:-180}"
  local elapsed=0
  local interval=3
  local container_id=""
  local health_status=""

  container_id="$(docker compose ps -q "${service}")"
  if [[ -z "${container_id}" ]]; then
    echo "[smoke] ERROR: service '${service}' container was not created."
    return 1
  fi

  echo "[smoke] Waiting for '${service}' to become healthy (timeout: ${timeout_seconds}s)"
  while (( elapsed < timeout_seconds )); do
    health_status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}")"
    if [[ "${health_status}" == "healthy" || "${health_status}" == "running" ]]; then
      echo "[smoke] '${service}' is ${health_status}"
      return 0
    fi

    sleep "${interval}"
    elapsed=$((elapsed + interval))
  done

  echo "[smoke] ERROR: service '${service}' did not become healthy in time."
  docker compose ps
  docker compose logs --tail 100 "${service}" || true
  return 1
}

check_http() {
  local name="$1"
  local url="$2"
  local expected_code="${3:-200}"
  local timeout_seconds="${4:-120}"
  local elapsed=0
  local interval=3
  local code=""

  echo "[smoke] Checking ${name} at ${url}"
  while (( elapsed < timeout_seconds )); do
    code="$(curl -s -o /dev/null -w "%{http_code}" "${url}" || true)"
    if [[ "${code}" == "${expected_code}" ]]; then
      echo "[smoke] ${name} responded with ${code}"
      return 0
    fi

    sleep "${interval}"
    elapsed=$((elapsed + interval))
  done

  echo "[smoke] ERROR: ${name} did not return ${expected_code}. Last code: ${code:-n/a}"
  return 1
}

wait_for_health "postgres"
wait_for_health "chromadb"
wait_for_health "backend"
wait_for_health "store-frontend"
wait_for_health "erp-frontend"

check_http "Backend health" "http://localhost:${BACKEND_PORT:-8000}/health" "200"
check_http "Store frontend" "http://localhost:${STORE_FRONTEND_PORT:-3000}" "200"
check_http "ERP frontend" "http://localhost:${ERP_FRONTEND_PORT:-3001}" "200"
check_http "Chroma heartbeat" "http://localhost:${CHROMA_PORT:-8001}/api/v1/heartbeat" "200"

echo "[smoke] Running PostgreSQL connectivity query"
docker compose exec -T postgres psql \
  -U "${POSTGRES_USER:-prodgrade}" \
  -d "${POSTGRES_DB:-prodgrade}" \
  -c "SELECT 1;"

echo "[smoke] All checks passed."
