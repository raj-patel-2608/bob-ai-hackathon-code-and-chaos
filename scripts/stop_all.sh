#!/usr/bin/env bash
# Stops the CrimeFIR services started by scripts/start_all.sh (Linux / macOS). Asks first (--yes to skip).
# Data stays in var/crimefir.db.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
YES=0; [[ "${1:-}" == "--yes" || "${1:-}" == "-y" ]] && YES=1
running=()
for svc in model_service core_api frontend; do
  pidf="$ROOT/var/run/$svc.pid"
  [[ -f "$pidf" ]] && kill -0 "$(cat "$pidf")" 2>/dev/null && running+=("$svc:$(cat "$pidf")")
done
if [[ ${#running[@]} -eq 0 ]]; then echo "No CrimeFIR services started by start_all.sh are running."; exit 0; fi
printf "  %s\n" "${running[@]}"
if [[ $YES == 0 ]]; then
  read -r -p "Stop these? [Y/n] " a
  case "$(echo "$a" | tr '[:upper:]' '[:lower:]')" in ""|y|yes) ;; *) echo "Nothing stopped."; exit 0 ;; esac
fi
for item in "${running[@]}"; do
  svc="${item%%:*}"; pid="${item##*:}"
  pkill -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null && echo "  stopped $svc (pid $pid)"
  rm -f "$ROOT/var/run/$svc.pid"
done
