# 🚀 CrimeFIR: FIR Intelligence & Crime Pattern Detector

> Reads raw FIR text, auto-drafts the NCRB crime classification, links FIRs across police stations and districts
> through hard evidence, flags repeat-offender clusters and writes station crime briefs. Investigators can query all
> of it in plain English through **IBM Bob**.

---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | Code & Chaos |
| **Track** | AI (IBM × NFSU Hackathon, Track 4 "AI & Predictive", Problem Statement 10) |
| **Team Lead** | TODO: name, email |
| **Members** | TODO: names |

---

## 🎯 Problem Statement

India's police hold crores of FIRs as free text (UP's CCTNS alone has 3+ crore) with no NLP layer. Serial offenders
such as Jamtara-style call centres reuse the same phones and mule accounts against victims in many districts, but
each FIR is filed at a different station and written differently, so inter-district links are never surfaced.
Investigating officers and Station House Officers lack a correlated, explainable picture of crime types, methods and
repeat offenders. [More in docs/problem-statement.md](docs/problem-statement.md)

---

## 💡 Solution

A three-tier pipeline:
- **Rules** extract hard evidence (phones in every Indian format, accounts, UPI IDs, IMEIs, vehicles, handles).
- **Laya**, an open-source decision model running locally, drafts the crime type and methods with a calibrated
  confidence.
- **IBM Granite on watsonx.ai** gives a grounded second opinion only when Laya is below 40% confident.

Shared evidence links FIRs, NetworkX finds repeat-offender clusters with a transparent risk score, and Granite
writes station briefs whose numbers are verified against the data. **IBM Bob** is the investigator's interface
through our MCP server. [More in docs/solution-overview.md](docs/solution-overview.md)

---

## ✨ Key Features

- **Auto-drafted NCRB I.I.F.-II:** crime major/minor head, 24 MO flags, victim profile, accused, with who decided
  and how confident. 93% major / 83% minor head accuracy on unseen FIRs.
- **Evidence-based repeat-offender clusters across stations and districts:** 100% cluster precision, no decoys
  linked. Each cluster has a graph, timeline, risk factors and suggested next actions.
- **System 1 / System 2 decisions:** Laya (local GPU, CPU fallback) plus IBM Granite (`granite-4-h-small`,
  watsonx.ai) for low-confidence FIRs, with schema-validated, text-grounded LLM output.
- **Station-level crime trend brief** written by IBM Granite, where every number is checked against computed facts
  (template fallback).
- **IBM Bob "FIR Analyst":** an MCP server with 12 tools, a custom mode with policing rules, and headless weekly
  briefs with `bob run`.

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python 3.12, JavaScript (React) |
| **Frameworks** | FastAPI, SQLAlchemy 2, Next.js 16 / React 19, Tailwind, react-force-graph (canvas graph), NetworkX, PyTorch, sentence-transformers, MCP Python SDK |
| **IBM Technologies** | IBM Bob (IDE + Bob Shell, MCP, custom mode), IBM watsonx.ai, IBM Granite 4 (`granite-4-h-small`), IBM Granite Embedding (`granite-embedding-30m-english`) |
| **Databases** | SQLite (WAL; PostgreSQL-ready through SQLAlchemy) |
| **Other** | Laya decision model (Convai Innovations, Apache 2.0), rapidfuzz, numpy, pytest |

---

## 📁 Repository Structure

```
├── src/
│   ├── core_api/        # FastAPI: ingestion, rules, job queue + worker, links, NetworkX clusters, briefs, evaluation
│   ├── model_service/   # FastAPI: Laya + Granite Embedding (GPU/CPU), watsonx Granite adapter (models.yaml)
│   ├── mcp_server/      # MCP server exposing CrimeFIR to IBM Bob
│   ├── frontend/        # Next.js UI
│   ├── dataset/         # 400 mock FIRs (NCRB I.I.F.-I layout), answer key, generator, real-case sources
│   ├── shared/          # crime taxonomy + dev-split calibration
│   └── .env.example
├── .bob/                # IBM Bob: MCP config, FIR Analyst mode, rules
├── scripts/             # setup / start / load-data / weekly Bob brief
├── docs/                # problem statement, solution overview, architecture, setup guide
├── demo/                # screenshots, video link, live-demo note
├── presentation/        # slides
└── submission.yaml
```

---

## ⚡ How to Run

> Full details, environment variables and troubleshooting: [`docs/setup-guide.md`](docs/setup-guide.md)

```powershell
# 1. Clone the repo
git clone https://github.com/gith-karan/bob-ai-hackathon-code-and-chaos.git
cd bob-ai-hackathon-code-and-chaos

# 2. Interactive setup: checks Python/Node/GPU, installs what is missing (asks Y/n first),
#    downloads the AI models, asks for the optional watsonx.ai credentials and tests them
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1          # Linux/macOS: bash scripts/setup.sh

# 3. Start everything with one command (waits until live, offers to load the 400 sample FIRs, opens the browser)
powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1      # Linux/macOS: bash scripts/start_all.sh
# open http://localhost:3000   ·   stop: scripts\stop_all.ps1 (Linux/macOS: bash scripts/stop_all.sh)
```
Unattended install: add `-Yes` (PowerShell) or `--yes` (bash). Setup can be re-run at any time; it only fixes what is
missing.

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🌐 Live Demo | [See demo/live-demo-url.txt](demo/live-demo-url.txt) (runs locally) |
| 🖼️ Screenshots | [See demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [See presentation/](presentation/) |

**Measured on the held-out test split (305 FIRs never used for tuning):**

| Output | Result |
|---|---|
| Crime major / minor head | 93.4% / 83.0% (Granite 40/40 on escalated FIRs) |
| Hard evidence extraction | 100% precision, 100% recall, 100% correct roles |
| Repeat-offender clusters | 100% precision, 93.7% recall, 11/12 planted gangs, 0 decoys |
| Accused names | 88% found |
| MO flags | F1 0.64 |

---

## ⚠️ Known Limitations

- **Synthetic data.** No public FIR text dataset exists (and real FIRs contain personal data), so results are
  measured on 400 mock FIRs grounded in real reported patterns. Real FIRs will be messier.
- **Names without a surname cannot be proven to be the same person.** "Pappu" and "Salim Sheikh" link only if some
  FIR states "Salim Sheikh alias Pappu". This is why one planted gang is recovered only partly (11/12).
- **MO flags are the weakest output** (F1 0.64). Six flags Laya cannot detect reliably are disabled instead of shown.
- **Pattern-only links are weak** on template-like data (dev precision 27% even at 0.97 similarity), so they are
  labelled as such and never used to flag anyone.
- **No authentication or role-based access** in this prototype. The reset endpoint is disabled only via
  `CRIMEFIR_ENV=production`.
- Low-confidence FIRs are sent to IBM watsonx.ai (cloud). Without credentials the system stays local and those FIRs
  go to officer review. Indicative BNS sections in the data are not legal advice.
- The IBM Bob integration (MCP tools, mode, `bob run` script) was tested through the MCP SDK and the live API. A
  full session inside Bob needs a Bob install and Bobcoins.

---

## 🏅 What We're Most Proud Of

- **Evidence first, honestly measured.** 100% cluster precision with zero decoys, 100% evidence extraction across
  messy formats, and an answer-key evaluation page, instead of claims.
- **A decision architecture that knows when it doesn't know.** Laya's calibrated confidence sends only ~12% of FIRs
  to IBM Granite, which got all 40 of them right. The full 400-FIR run used about 85k tokens.
- **Grounded AI.** LLM names must appear in the FIR, claimed fraud personas never count as identities, and
  station-brief numbers are verified, so the system never invents a link or a figure.
