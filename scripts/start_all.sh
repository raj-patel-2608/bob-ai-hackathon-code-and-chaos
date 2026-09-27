#!/usr/bin/env bash
# Starts the whole CrimeFIR system with one command (Linux / macOS) and waits until it is live.
# Services run in the background; logs in var/logs/, process ids in var/run/. Stop with: bash scripts/stop_all.sh
#
#   bash scripts/start_all.sh                 # asks before loading the sample data
#   bash scripts/start_all.sh --load-sample   # load the 400 sample FIRs if the database is empty
set -uo pipefail
LOAD=0; YES=0
for a in "$@"; do case "$a" in --load-sample) LOAD=1 ;; --yes|-y) YES=1 ;; esac; done
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/src"
mkdir -p "$ROOT/var/logs" "$ROOT/var/run"
export PYTHONIOENCODING=utf-8 HF_HUB_DISABLE_SYMLINKS_WARNING=1

missing=""
for svc in model_service core_api; do [[ -x "$SRC/$svc/.venv/bin/python" ]] || missing="$missing $svc"; done
[[ -d "$SRC/frontend/node_modules" ]] || missing="$missing frontend"
if [[ -n "$missing" ]]; then echo "Not installed yet:$missing. Run first:  bash scripts/setup.sh"; exit 1; fi

up() { curl -fs -m 3 -o /dev/null "$1"; }
start() {   # start name dir port health command...
  local name="$1" dir="$2" port="$3" health="$4"; shift 4
  if up "$health"; then printf "  %-14s already running on port %s\n" "$name" "$port"; return; fi
  (cd "$SRC/$dir" && nohup "$@" > "$ROOT/var/logs/$dir.log" 2>&1 & echo $! > "$ROOT/var/run/$dir.pid")
  printf "  %-14s starting on port %s (log: var/logs/%s.log)\n" "$name" "$port" "$dir"
}
start "model service" model_service 8100 http://127.0.0.1:8100/v1/health .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
start "core API" core_api 8000 http://127.0.0.1:8000/api/health/live .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
start "frontend" frontend 3000 http://localhost:3000/ npm run dev

echo; echo "Waiting for the services (the first start may download the AI models; later starts take ~20-60 s)..."
wait_for() {   # wait_for name url seconds
  local t=0; printf "  %-14s " "$1"
  until up "$2"; do
    if (( t >= $3 )); then printf "\033[31m not responding after %ss - see var/logs/\033[0m\n" "$3"; exit 1; fi
    printf "."; sleep 3; t=$((t + 3))
  done
  printf "\033[32m live (%ss)\033[0m\n" "$t"
}
wait_for "model service" http://127.0.0.1:8100/v1/health 600
wait_for "core API" http://127.0.0.1:8000/api/health/live 120
wait_for "frontend" http://localhost:3000/ 180

MODE="$(curl -s -m 10 http://127.0.0.1:8000/api/health/ready | python3 -c 'import sys,json
d=json.load(sys.stdin); print("mode:", d.get("mode"))
for k,c in d["checks"]["model_service"].get("capabilities",{}).items():
    print(f"  {k:<10}", (c.get("model_id","")+" on "+str(c.get("device"))) if c.get("available") else "not available: "+str(c.get("reason")))' 2>/dev/null)"
echo; echo "  ${MODE:-(could not read readiness details)}"

TOTAL="$(curl -s -m 10 http://127.0.0.1:8000/api/dashboard | python3 -c 'import sys,json; print(json.load(sys.stdin).get("total_firs",""))' 2>/dev/null)"
if [[ "$TOTAL" == "0" ]]; then
  if [[ $LOAD == 0 && $YES == 0 ]]; then
    read -r -p "  The database is empty. Load the 400 sample FIRs now (6-10 minutes of processing)? [Y/n] " a
    case "$(echo "$a" | tr '[:upper:]' '[:lower:]')" in ""|y|yes) LOAD=1 ;; esac
  fi
  [[ $YES == 1 ]] && LOAD=1
  if [[ $LOAD == 1 ]]; then
    curl -s -F "file=@$SRC/dataset/firs_main.txt" http://127.0.0.1:8000/api/batches >/dev/null \
      && echo "  Uploaded the sample FIRs; processing continues in the background (see the Add FIRs page)."
  fi
elif [[ -n "$TOTAL" ]]; then echo "  Database: $TOTAL FIRs."; fi

echo; printf "\033[32mCrimeFIR is live:  http://localhost:3000   (API docs: http://127.0.0.1:8000/docs)\033[0m\n"
echo "Stop everything:   bash scripts/stop_all.sh"
if command -v xdg-open >/dev/null 2>&1; then xdg-open http://localhost:3000 >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then open http://localhost:3000 || true; fi
