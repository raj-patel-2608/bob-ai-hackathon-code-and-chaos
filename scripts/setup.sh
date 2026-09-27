#!/usr/bin/env bash
# CrimeFIR interactive setup (Linux / macOS). Checks everything first and asks before installing anything.
#
#   bash scripts/setup.sh           # interactive (Y/n questions)
#   bash scripts/setup.sh --yes     # answer "yes" to everything (unattended)
#
# Steps: 1 prerequisites  2 Python packages  3 frontend packages  4 AI models  5 config + watsonx.ai  6 tests  7 start
# Safe to run again: things already in place are only checked, never reinstalled.
set -uo pipefail
YES=0; NOSTART=0
for a in "$@"; do case "$a" in --yes|-y) YES=1 ;; --no-start) NOSTART=1 ;; esac; done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/src"
DOCTOR="$ROOT/scripts/doctor.py"
export PYTHONIOENCODING=utf-8 HF_HUB_DISABLE_SYMLINKS_WARNING=1
KEYS=(); VALS=()          # summary (plain arrays: macOS ships bash 3.2)

c() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
step() { echo; c "36" "[$1/7] $2"; }
ok() { c "32" "  OK       $1"; }
miss() { c "33" "  MISSING  $1"; }
fail() { c "31" "  FAIL     $1"; }
info() { echo "           $1"; }
put() {
  local i
  for i in "${!KEYS[@]}"; do [[ "${KEYS[$i]}" == "$1" ]] && { VALS[$i]="$2"; return; }; done
  KEYS+=("$1"); VALS+=("$2")
}
get() { local i; for i in "${!KEYS[@]}"; do [[ "${KEYS[$i]}" == "$1" ]] && { echo "${VALS[$i]}"; return; }; done; }
lower() { echo "$1" | tr '[:upper:]' '[:lower:]'; }
ask() {   # ask "question" [Y|N]
  local def="${2:-Y}" hint="[Y/n]" a
  [[ "$def" == "N" ]] && hint="[y/N]"
  if [[ $YES == 1 ]]; then echo "  $1 -> yes (--yes)"; return 0; fi
  while true; do
    read -r -p "  $1 $hint " a
    [[ -z "$a" ]] && { [[ "$def" == "Y" ]]; return; }
    case "$(lower "$a")" in y|yes) return 0 ;; n|no) return 1 ;; *) echo "  Please answer y or n." ;; esac
  done
}

echo "CrimeFIR setup - repo: $ROOT"
echo "Nothing is installed without asking. Press Enter to accept the default shown in capitals."
OS="$(uname -s)"

# ------------------------------------------------------------------------------------------ 1 prerequisites
step 1 "Prerequisites"
PY=""
for cand in python3.12 python3.11 python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$cand"; break
  fi
done
if [[ -n "$PY" ]]; then ok "Python $("$PY" -c 'import sys;print("%d.%d.%d" % sys.version_info[:3])') ($PY)"
else
  miss "Python 3.11+ (3.12 recommended). Install it, e.g.:"
  info "Ubuntu/Debian: sudo apt install python3.12 python3.12-venv    macOS: brew install python@3.12"
  exit 1
fi
"$PY" -c 'import venv, ensurepip' 2>/dev/null || { miss "python venv module (Ubuntu/Debian: sudo apt install python3-venv)"; exit 1; }
if command -v node >/dev/null 2>&1 && node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>20||(a==20&&b>=9)?0:1)'; then
  ok "Node.js $(node -v), npm $(npm -v)"
else
  miss "Node.js 20.9+ (https://nodejs.org, or: nvm install --lts / brew install node)"; exit 1
fi
GPU=0
if command -v nvidia-smi >/dev/null 2>&1 && G=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null) && [[ -n "$G" ]]; then
  GPU=1; ok "NVIDIA GPU: $G (models run on the GPU)"
else info "No NVIDIA GPU found: the AI models will run on the CPU (slower, but everything works)."; fi
put "Prerequisites" "OK"

# ------------------------------------------------------------------------------------------ 2 python packages
step 2 "Python packages (core API, model service, MCP server for IBM Bob)"
install_reqs() {   # install_reqs svc dir venv_python
  local svc="$1" dir="$2" vpy="$3" req="$2/requirements.txt"
  "$vpy" -m pip install --upgrade pip --quiet || return 1
  if [[ "$svc" == "model_service" && ( $GPU == 0 || "$OS" == "Darwin" ) ]]; then
    local torch_line tmp
    torch_line="$(grep -E '^torch==' "$req" | sed 's/+.*$//')"
    tmp="$(mktemp)"; grep -vE '^(torch==|--extra-index-url)' "$req" > "$tmp"
    if [[ "$OS" == "Darwin" ]]; then
      info "macOS: installing the standard PyTorch build (CPU / Apple GPU)"
      "$vpy" -m pip install "$torch_line" || return 1
    elif ask "No NVIDIA GPU: install the smaller CPU-only PyTorch instead of the CUDA build?" Y; then
      "$vpy" -m pip install "$torch_line" --index-url https://download.pytorch.org/whl/cpu || return 1
    else
      tmp="$req"
    fi
    "$vpy" -m pip install -r "$tmp" || return 1
    return 0
  fi
  "$vpy" -m pip install -r "$req"
}
for svc in core_api model_service mcp_server; do
  dir="$SRC/$svc"; vpy="$dir/.venv/bin/python"
  echo "  - $svc"
  if [[ ! -x "$vpy" ]]; then
    miss "no virtual environment in src/$svc/.venv"
    if ! ask "Create it and install the $svc packages?" Y; then put "$svc" "skipped"; continue; fi
    "$PY" -m venv "$dir/.venv" || { fail "could not create the virtual environment"; put "$svc" "FAILED"; continue; }
  else
    if out="$("$vpy" "$DOCTOR" reqs "$dir/requirements.txt")"; then ok "all packages installed"; put "$svc" "OK"; continue; fi
    echo "$out" | sed 's/^/           /'
    if ! ask "Install / update these packages?" Y; then put "$svc" "incomplete (skipped)"; continue; fi
  fi
  if install_reqs "$svc" "$dir" "$vpy"; then ok "$svc packages installed"; put "$svc" "OK"
  else fail "pip install failed for $svc (see above)"; put "$svc" "FAILED"; fi
done

# ------------------------------------------------------------------------------------------ 3 frontend
step 3 "Frontend packages (Next.js)"
cd "$SRC/frontend" || exit 1
if [[ -d node_modules ]] && npm ls --depth=0 --silent >/dev/null 2>&1; then ok "node_modules up to date"; put frontend "OK"
else
  miss "frontend packages not installed or out of date"
  if ask "Install them now (npm ci, ~400 MB)?" Y; then
    if { [[ -f package-lock.json ]] && npm ci; } || { [[ ! -f package-lock.json ]] && npm install; }; then ok "frontend packages installed"; put frontend "OK"
    else fail "npm failed"; put frontend "FAILED"; fi
  else put frontend "skipped"; fi
fi
[[ -f .env.local ]] || { cp .env.local.example .env.local; ok "created src/frontend/.env.local"; }
cd "$ROOT" || exit 1

# ------------------------------------------------------------------------------------------ 4 models
step 4 "AI models"
MSPY="$SRC/model_service/.venv/bin/python"
if [[ ! -x "$MSPY" || "$(get model_service)" != "OK" ]]; then
  miss "model service packages are not installed, so the models cannot be checked"; put models "not checked"
else
  "$MSPY" "$DOCTOR" gpu || true
  if "$MSPY" "$DOCTOR" models; then put models "OK"
  else
    info "Without them the model service downloads them on its first start instead."
    if ask "Download the missing models now (Laya ~1.7 GB, Granite Embedding ~65 MB)?" Y; then
      if "$MSPY" "$DOCTOR" models --download; then put models "OK"; else put models "FAILED (check access to huggingface.co)"; fi
    else put models "download on first start"; fi
  fi
fi

# ------------------------------------------------------------------------------------------ 5 configuration
step 5 "Configuration and IBM watsonx.ai"
ENVF="$SRC/.env"
if [[ -f "$ENVF" ]]; then ok "src/.env exists"; else cp "$SRC/.env.example" "$ENVF"; ok "created src/.env from src/.env.example"; fi
getv() { grep -E "^\s*$1\s*=" "$ENVF" | head -1 | cut -d= -f2- | tr -d '"' | xargs; }
setv() {
  "$PY" - "$ENVF" "$1" "$2" <<'PYEOF'
import re, sys
path, name, value = sys.argv[1:]
lines = open(path, encoding="utf-8").read().splitlines()
for i, line in enumerate(lines):
    if re.match(rf"^\s*#?\s*{name}\s*=", line):
        lines[i] = f"{name}={value}"; break
else:
    lines.append(f"{name}={value}")
open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
PYEOF
}
read_watsonx() {
  info "Create an API key at https://cloud.ibm.com/iam/apikeys; the project ID is on your watsonx.ai project's Manage tab."
  local key project r region
  read -r -s -p "  IBM Cloud API key (input hidden): " key; echo
  read -r -p "  watsonx.ai project ID: " project
  echo "  Region: 1) Frankfurt eu-de  2) Dallas us-south  3) London eu-gb  4) Tokyo jp-tok  5) Sydney au-syd"
  read -r -p "  Choose 1-5 [1]: " r
  case "${r:-1}" in 2) region=us-south ;; 3) region=eu-gb ;; 4) region=jp-tok ;; 5) region=au-syd ;; *) region=eu-de ;; esac
  [[ -n "$key" ]] && setv WATSONX_API_KEY "$key"
  [[ -n "$project" ]] && setv WATSONX_PROJECT_ID "$project"
  setv WATSONX_URL "https://$region.ml.cloud.ibm.com"
  ok "saved to src/.env (git-ignored; never commit it)"
}
KEY="$(getv WATSONX_API_KEY)"; PROJ="$(getv WATSONX_PROJECT_ID)"
CONFIGURED=1
case "$KEY" in ""|your_ibm_cloud_api_key) CONFIGURED=0 ;; esac
case "$PROJ" in ""|your_watsonx_project_id) CONFIGURED=0 ;; esac
if [[ $CONFIGURED == 0 ]]; then
  miss "watsonx.ai credentials are not set (optional)"
  info "Without them CrimeFIR still runs fully locally: uncertain FIRs go to officer review, briefs use a template."
  if ask "Enter IBM watsonx.ai credentials now?" Y; then
    if [[ $YES == 1 ]]; then info "skipped in --yes mode (needs typing)"; else read_watsonx; CONFIGURED=1; fi
  fi
fi
if [[ $CONFIGURED == 1 && "$(get model_service)" == "OK" ]]; then
  if ! "$MSPY" "$DOCTOR" watsonx && [[ $YES == 0 ]] && ask "The check failed. Re-enter the credentials?" Y; then read_watsonx; fi
  if "$MSPY" "$DOCTOR" watsonx >/dev/null; then
    put "watsonx.ai" "OK"
    if ask "Send one tiny test request (~20 tokens) to confirm the project ID?" Y; then
      "$MSPY" "$DOCTOR" watsonx --ping || put "watsonx.ai" "key OK, project check FAILED"
    fi
  else put "watsonx.ai" "FAILED (runs without the LLM)"; fi
elif [[ $CONFIGURED == 0 ]]; then put "watsonx.ai" "not configured (optional)"; fi
# IBM Bob MCP config uses the Windows interpreter path; point it at the Linux/macOS one
if grep -q 'Scripts/python.exe' "$ROOT/.bob/mcp.json" 2>/dev/null && ask "Update .bob/mcp.json to use src/mcp_server/.venv/bin/python (for IBM Bob)?" Y; then
  sed -i.bak 's#src/mcp_server/.venv/Scripts/python.exe#src/mcp_server/.venv/bin/python#' "$ROOT/.bob/mcp.json" && rm -f "$ROOT/.bob/mcp.json.bak"
  ok ".bob/mcp.json updated"
fi

# ------------------------------------------------------------------------------------------ 6 tests
step 6 "Automated tests (optional)"
CAPY="$SRC/core_api/.venv/bin/python"
if [[ "$(get core_api)" == "OK" ]] && ask "Run the core API tests (no GPU or internet needed, ~1-2 minutes)?" N; then
  if (cd "$SRC/core_api" && "$CAPY" -m pytest -q -p no:warnings); then put tests "passed"; else put tests "FAILED"; fi
else put tests "not run"; fi

# ------------------------------------------------------------------------------------------ 7 summary + start
step 7 "Summary"
for i in "${!KEYS[@]}"; do
  k="${KEYS[$i]}"; v="${VALS[$i]}"
  if [[ "$v" == "OK" || "$v" == "passed" ]]; then col=32; elif [[ "$v" == *FAIL* ]]; then col=31; else col=33; fi
  printf "  %-16s \033[%sm%s\033[0m\n" "$k" "$col" "$v"
done
BLOCK=""
for k in core_api model_service frontend; do [[ "$(get "$k")" == "OK" ]] || BLOCK="$BLOCK $k"; done
if [[ -n "$BLOCK" ]]; then c 33 "  Not ready to start:$BLOCK. Fix the items above and run setup.sh again."; exit 1; fi
c 32 "  Setup complete. To start CrimeFIR later:  bash scripts/start_all.sh"
if [[ $NOSTART == 0 ]] && ask "Start CrimeFIR now?" Y; then
  if [[ $YES == 1 ]]; then exec bash "$ROOT/scripts/start_all.sh" --yes; else exec bash "$ROOT/scripts/start_all.sh"; fi
fi
