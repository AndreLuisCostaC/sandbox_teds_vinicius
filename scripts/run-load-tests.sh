#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORTS_DIR="${ROOT_DIR}/reports"
mkdir -p "${REPORTS_DIR}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
REPORT_FILE="${REPORTS_DIR}/load-test-${TIMESTAMP}.md"

run_test() {
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
  echo "# Load Test Report"
  echo ""
  echo "- Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- Goal: verify endpoint and dashboard responsiveness under concurrency."
  echo ""
} > "${REPORT_FILE}"

cd "${ROOT_DIR}" || exit 1

run_test \
  "Search API Load Test" \
  python3 src/backend-generic/scripts/load_test_search.py

run_test \
  "Order API Load Test" \
  python3 src/backend-generic/scripts/load_test_orders.py

run_test \
  "ERP Dashboard API Load Test" \
  python3 src/backend-generic/scripts/load_test_dashboard.py

echo "Load test report written to ${REPORT_FILE}"
