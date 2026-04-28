#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "backend/.venv/bin/activate" ]; then
  echo "Error: backend/.venv not found. Create it with: python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi

# shellcheck disable=SC1091
source backend/.venv/bin/activate

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "⚠️  ANTHROPIC_API_KEY is not set — Step 9 will stream mock text. Cache mode still works."
else
  echo "✓ ANTHROPIC_API_KEY detected."
fi

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "Shutting down..."
  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  echo "Stopped."
  exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting backend on http://localhost:8000 ..."
(cd backend && uvicorn main:app --reload --port 8000) &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:5173 ..."
echo ""
echo "→ Open http://localhost:5173 when Vite is ready. Press Ctrl+C to stop both."
echo ""

(cd frontend && npm run dev) &
FRONTEND_PID=$!

wait "$FRONTEND_PID"
cleanup
