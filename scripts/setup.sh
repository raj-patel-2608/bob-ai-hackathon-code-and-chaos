#!/usr/bin/env bash
# One-time setup (Linux / macOS). Creates a virtual environment per Python service and installs the frontend.
set -euo pipefail
cd "$(dirname "$0")/../src"
for svc in core_api model_service mcp_server; do
  echo "== $svc"
  (cd "$svc" && python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip >/dev/null \
    && .venv/bin/python -m pip install -r requirements.txt)
done
echo "== frontend"
(cd frontend && npm install && { [ -f .env.local ] || cp .env.local.example .env.local; })
[ -f .env ] || { cp .env.example .env; echo "Created src/.env - add watsonx credentials (optional)"; }
echo "Setup complete. Next: scripts/start_all.sh"
