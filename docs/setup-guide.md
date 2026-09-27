# Setup Guide

> **This file is read by the automated evaluation pipeline. Be precise and complete.**

## Prerequisites
| Tool | Version | Notes |
|---|---|---|
| Python | 3.12 (3.11+ works) | `python --version` |
| Node.js + npm | Node 20.9+ (tested 22.21) | `node -v` |
| Git | any | |
| Disk | ~12 GB free | PyTorch (~3 GB) + models downloaded on first start (Laya ~1.7 GB, Granite Embedding ~0.1 GB) |
| GPU | optional | NVIDIA with ≥ 2 GB free VRAM is used automatically (tested on an RTX 3050 laptop with 4 GB). Without a GPU everything runs on CPU (slower). |
| Internet | first start only | To download models from Hugging Face. watsonx.ai calls need internet. |
| IBM Cloud / watsonx.ai | optional | For the Granite LLM tier. Without it, low-confidence FIRs go to the review queue and briefs use a template. |
| IBM Bob | optional | For the Bob / MCP integration (see the last section) |

## Environment Variables
Copy `src/.env.example` to `src/.env` (the setup script does this). Never commit `src/.env`.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `WATSONX_API_KEY` | for the LLM tier | none | IBM Cloud API key (IAM → API keys) |
| `WATSONX_PROJECT_ID` | for the LLM tier | none | watsonx.ai project id |
| `WATSONX_URL` | for the LLM tier | `https://us-south.ml.cloud.ibm.com` | Region endpoint, e.g. `https://eu-de.ml.cloud.ibm.com` |
| `CRIMEFIR_DATABASE_URL` | no | `sqlite:///<repo>/var/crimefir.db` | Any SQLAlchemy URL |
| `CRIMEFIR_MODEL_SERVICE_URL` | no | `http://127.0.0.1:8100` | Where core-api finds the model service |
| `CRIMEFIR_DECISION_MIN_CONFIDENCE` | no | `0.40` | Laya answers below this go to the Granite LLM |
| `CRIMEFIR_LLM_MONTHLY_TOKEN_BUDGET` | no | `250000` | Stops LLM calls before the watsonx Lite quota runs out |
| `CRIMEFIR_SOFT_LINK_MIN_SIMILARITY` | no | `0.97` | Threshold for pattern-only links |
| `CRIMEFIR_ENV` | no | `development` | `production` disables the reset endpoint |
| `NEXT_PUBLIC_API_URL` (`src/frontend/.env.local`) | no | `http://localhost:8000` | API URL used by the browser |
| `CRIMEFIR_API_URL` (in `.bob/mcp.json`) | no | `http://127.0.0.1:8000` | API URL used by the MCP server |

Models are selected in `src/model_service/models.yaml` (decision, embedding, generator; device `auto` = GPU if
available, else CPU).

## Installation
```bash
git clone https://github.com/gith-karan/bob-ai-hackathon-code-and-chaos.git
cd bob-ai-hackathon-code-and-chaos
```
**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```
**Linux / macOS:**
```bash
bash scripts/setup.sh
```
Both scripts create `src/core_api/.venv`, `src/model_service/.venv` and `src/mcp_server/.venv`, install each
service's `requirements.txt`, run `npm install` in `src/frontend`, and create `src/.env` from the example.

Manual equivalent for one service (Windows paths shown; on Linux use `.venv/bin/python`):
```bash
cd src/core_api && python -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt
```

## Running the Project
**Windows:** each service opens in its own window.
```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
```
**Linux / macOS:**
```bash
bash scripts/start_all.sh
```
Or start the three services manually, in this order, each in its own terminal:
```bash
cd src/model_service && .venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
cd src/core_api      && .venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
cd src/frontend      && npm run dev
```
The first start of the model service downloads the models (a few minutes). Later starts take about 20 seconds.

**Load the data** (400 FIRs; about 6 minutes on a 4 GB laptop GPU, longer on CPU):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\load_dataset.ps1
```
```bash
curl -F "file=@src/dataset/firs_main.txt" http://127.0.0.1:8000/api/batches
```
Or open http://localhost:3000/upload and choose `src/dataset/firs_main.txt`.

**Live-demo batch** (6 new FIRs, 3 of which join existing gangs):
`scripts\load_dataset.ps1 -File src\dataset\demo_live_batch.txt`

**Standalone set** (60 unrelated FIRs; expect no new groups):
`scripts\load_dataset.ps1 -File src\dataset\firs_unrelated.txt`

**Removing data:** on *Add FIRs*, each uploaded batch has a **Delete** button (in-page confirmation; its FIRs, analysis,
evidence and links are removed and the groups recalculated). *Delete all data…* asks you to type `DELETE`.
API: `DELETE /api/batches/{id}`, `POST /api/system/reset` (disabled when `CRIMEFIR_ENV=production`).

## Verifying It Works
1. http://127.0.0.1:8100/v1/health lists `decision`, `embedding` (device `cuda` or `cpu`) and `generator`
   (`ibm/granite-4-h-small`, or unavailable with the reason if no watsonx credentials).
2. http://127.0.0.1:8000/api/health/ready returns `"status": "ready"` and `"mode": "full"`
   (or `rules-only` if the model service is down).
3. http://localhost:3000 shows the dashboard. After loading data you should see 400 FIRs and 12 flagged clusters.
4. **AI accuracy** page → *Evaluate test split*. You should see roughly: crime major 93%, minor 83%, evidence
   extraction 100%/100%, cluster precision 100%, 11/12 gangs (numbers for the LLM tier require watsonx
   credentials).
5. Interactive API docs: http://127.0.0.1:8000/docs

**Automated tests** (no GPU or network needed; they use fake models and a temporary database):
```bash
cd src/core_api      && .venv/Scripts/python -m pytest          # 28 tests incl. a full 400-FIR regression run
cd src/model_service && .venv/Scripts/python -m pytest tests    # 7 tests (GPU/CPU fallback, watsonx adapter)
cd src/mcp_server    && .venv/Scripts/python -m pytest          # 3 tests
python src/dataset/generator/validate.py                        # dataset / answer-key consistency
```

## IBM Bob integration
1. Install IBM Bob (bob.ibm.com/download) and sign in with your IBMid.
2. Open this repository folder in Bob. Project-level config is already in `.bob/`:
   - `.bob/mcp.json` registers the `crimefir` MCP server (Windows interpreter path; on Linux/macOS change
     `command` to `src/mcp_server/.venv/bin/python`).
   - `.bob/custom_modes.yaml` adds the **🕵️ FIR Analyst** mode, with rules in `.bob/rules-fir-analyst/`.
3. With the core API running, choose the FIR Analyst mode and ask, for example: *"List the high-risk
   repeat-offender clusters and what to do first"* or *"Write a crime brief for Navrangpura for the last 30 days"*.
4. Headless weekly brief (Bob Shell v2): `scripts\weekly_brief.ps1 -Station "Navrangpura"`
   (runs `bob run --format json --max-cost 2 …` and saves to `var/briefs/`).

## Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| UI says "Could not reach the CrimeFIR API" | core API not running | Start `src/core_api` (port 8000); check `var/logs/core_api.log` |
| Sidebar mode shows `rules-only` | model service not running or still loading | Start `src/model_service`; wait for "model service ready" in its log |
| Many FIRs in "needs review" | watsonx not configured, so low-confidence FIRs got no second opinion | Add `WATSONX_*` to `src/.env`, restart the model service, then `POST /api/system/reprocess-llm` |
| `generator unavailable: none of [...] is available` | Granite model not offered in your watsonx region | Add a model your region lists to `model_candidates` in `models.yaml` |
| `IBM Cloud IAM token request failed (400)` | wrong API key | Create a new key in IBM Cloud → IAM → API keys |
| Model service logs "loaded on cpu" | no CUDA GPU / not enough free VRAM | Expected. It still works, just slower. Close other GPU apps to use the GPU. |
| `torch` install is slow or huge | CUDA build of PyTorch (~3 GB) | Expected once. It also runs on CPU-only machines. |
| Port 8000 / 8100 / 3000 already in use | another program | Stop it, or change the port and `CRIMEFIR_MODEL_SERVICE_URL` / `NEXT_PUBLIC_API_URL` |
| Changed a table and the API errors on startup | SQLite schema from an older version | Delete `var/crimefir.db` (demo data only) and reload the dataset |
| `scripts\*.ps1` blocked | PowerShell execution policy | Run with `powershell -ExecutionPolicy Bypass -File …` |
