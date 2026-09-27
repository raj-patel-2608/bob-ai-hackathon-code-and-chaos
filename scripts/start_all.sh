#!/usr/bin/env bash
# Starts the three CrimeFIR services in the background (Linux / macOS). Logs go to var/logs/. Ctrl+C stops all.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/var/logs"
(cd "$ROOT/src/model_service" && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100 \
  > "$ROOT/var/logs/model_service.log" 2>&1) &
(cd "$ROOT/src/core_api" && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
  > "$ROOT/var/logs/core_api.log" 2>&1) &
(cd "$ROOT/src/frontend" && npm run dev > "$ROOT/var/logs/frontend.log" 2>&1) &
trap 'kill 0' INT TERM
echo "model service :8100, core API :8000 (docs /docs), frontend http://localhost:3000 - logs in var/logs/"
echo "Load data:  curl -F file=@src/dataset/firs_main.txt http://127.0.0.1:8000/api/batches"
wait
