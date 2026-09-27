# Source code

| Folder | What it is | Run / test |
|---|---|---|
| `core_api/` | FastAPI core: ingestion, FIR parser, rule-based evidence extraction, DB-backed job queue + background worker, Laya / LLM decisions, evidence & pattern links, NetworkX repeat-offender clusters, station facts & briefs, evaluation, REST API (`/docs`) | `uvicorn app.main:app --port 8000` · `pytest` |
| `model_service/` | FastAPI model service: the only process that loads models. Provider adapters chosen in `models.yaml`: Laya (decision), IBM Granite Embedding (embedding), IBM Granite on watsonx.ai (generator). GPU-first with CPU fallback. | `uvicorn app.main:app --port 8100` · `pytest tests` |
| `mcp_server/` | MCP server exposing the core API to IBM Bob (12 tools) | started by Bob via `.bob/mcp.json` · `pytest` |
| `frontend/` | Next.js 16 UI | `npm run dev` |
| `dataset/` | 400 mock FIRs (NCRB I.I.F.-I layout), answer key, live-demo batch, generator + validator, real-case sources | `python generator/build.py` · `python generator/validate.py` |
| `shared/` | `taxonomy.json` (crime heads, MO flags) and `calibration.json` (thresholds tuned on the dev split) | `core_api/scripts/calibrate.py` |
| `.env.example` | Every environment variable, with defaults | copy to `.env` |

Each Python service has its own `requirements.txt` and `.venv`, created by `scripts/setup.ps1` or
`scripts/setup.sh`.

## Utility scripts (`core_api/scripts/`)
- `calibrate.py`: tunes per-MO-flag thresholds and checks pattern-link precision on the dev split only
  (`--apply` re-applies them).
- `reapply_llm_grounding.py`: re-applies the name-grounding rules to stored LLM output without new LLM calls.

Phase-0 model studies are in `model_service/scripts/spike_laya*.py`.
