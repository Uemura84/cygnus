#!/usr/bin/env bash
# Kill any orphaned uvicorn/vite processes bound to 8000 / 5173.

killed_any=0

for port in 8000 5173; do
  pids=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Killing processes on port $port: $pids"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
    killed_any=1
  fi
done

# Fallback: pattern match in case the process isn't bound yet.
for pattern in "uvicorn main:app" "vite"; do
  pids=$(pgrep -f "$pattern" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Killing '$pattern' processes: $pids"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    killed_any=1
  fi
done

if [ "$killed_any" -eq 0 ]; then
  echo "No backend/frontend processes found on ports 8000 or 5173."
else
  echo "Done."
fi
