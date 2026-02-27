#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORTS_DIR="${ROOT_DIR}/reports"
mkdir -p "${REPORTS_DIR}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
REPORT_FILE="${REPORTS_DIR}/security-scan-${TIMESTAMP}.md"

run_scan() {
  local label="$1"
  shift
  echo "### ${label}" >> "${REPORT_FILE}"
  echo "" >> "${REPORT_FILE}"
  echo '```text' >> "${REPORT_FILE}"
  if "$@" >> "${REPORT_FILE}" 2>&1; then
    echo "" >> "${REPORT_FILE}"
    echo "Result: PASS" >> "${REPORT_FILE}"
  else
    echo "" >> "${REPORT_FILE}"
    echo "Result: FAIL" >> "${REPORT_FILE}"
  fi
  echo '```' >> "${REPORT_FILE}"
  echo "" >> "${REPORT_FILE}"
}

{
  echo "# Security Scan Report"
  echo ""
  echo "- Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Goal: static checks for common vulnerabilities and dependency risk."
  echo ""
} > "${REPORT_FILE}"

cd "${ROOT_DIR}" || exit 1

if python3 -m bandit --version >/dev/null 2>&1; then
  run_scan \
    "Bandit - Backend Code" \
    python3 -m bandit -q -r src/backend-generic/app
else
  {
    echo "### Bandit - Backend Code"
    echo ""
    echo '```text'
    echo "Result: SKIPPED"
    echo "bandit is not installed in the current Python environment."
    echo "Install suggestion: python3 -m pip install bandit"
    echo '```'
    echo ""
  } >> "${REPORT_FILE}"
fi

run_scan \
  "npm audit (high+) - frontend-admin" \
  bash -lc "cd src/frontend-admin && npm audit --audit-level=high"

run_scan \
  "npm audit (high+) - frontend-ecom" \
  bash -lc "cd src/frontend-ecom && npm audit --audit-level=high"

{
  echo "### OWASP ZAP (Optional)"
  echo ""
  echo '```text'
  echo "Not executed automatically."
  echo "Example:"
  echo "docker run --rm -t owasp/zap2docker-stable zap-baseline.py \\"
  echo "  -t http://host.docker.internal:8000 -m 5"
  echo '```'
  echo ""
} >> "${REPORT_FILE}"

echo "Security scan report written to ${REPORT_FILE}"
