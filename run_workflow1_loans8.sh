#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOANS8_DIR="$ROOT_DIR/loans8"
WORKFLOW1_DIR="$ROOT_DIR/workflow1"

LOANS8_HOST="${LOANS8_HOST:-127.0.0.1}"
LOANS8_PORT="${LOANS8_PORT:-8000}"
LOANS8_API_BASE="http://${LOANS8_HOST}:${LOANS8_PORT}"
PYTHON_BIN="${PYTHON_BIN:-python}"

cleanup() {
  if [[ -n "${LOANS8_PID:-}" ]]; then
    kill "$LOANS8_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cd "$LOANS8_DIR"
"$PYTHON_BIN" -m uvicorn app:app --host "$LOANS8_HOST" --port "$LOANS8_PORT" --reload &
LOANS8_PID=$!

printf "Waiting for loans8 API at %s...\n" "$LOANS8_API_BASE"
for _ in {1..60}; do
  if curl -sf "$LOANS8_API_BASE/docs" >/dev/null 2>&1; then
    printf "loans8 API is up.\n"
    break
  fi
  sleep 0.5
  if ! kill -0 "$LOANS8_PID" >/dev/null 2>&1; then
    printf "loans8 API exited unexpectedly.\n" >&2
    exit 1
  fi
  if [[ $_ -eq 60 ]]; then
    printf "Timed out waiting for loans8 API.\n" >&2
    exit 1
  fi
  done

cd "$WORKFLOW1_DIR"
export LOANS8_API_BASE
python main.py
