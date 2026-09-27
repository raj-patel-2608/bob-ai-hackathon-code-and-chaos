# Solution Overview: CrimeFIR

**CrimeFIR reads raw FIR text, auto-drafts the NCRB crime classification (I.I.F.-II), extracts hard evidence,
links FIRs across stations and districts, flags repeat-offender clusters and writes station crime briefs.
Investigators can query all of it in plain English through IBM Bob.**

## Core mechanism: evidence first, AI where it helps, a human decides
1. **Hard evidence by rules, not AI.** Phones (all Indian formats), bank accounts, UPI IDs, IMEIs, vehicle numbers
   and online handles are extracted with deterministic patterns and normalised (`98765 43210` → `+919876543210`).
   Each carries a **role** (offender / stolen property / complainant), so a complainant's own number never links
   cases.
2. **System 1: Laya** (open-source decision model by Convai Innovations, India, Apache 2.0), run locally on the GPU.
   It answers typed questions about each FIR in one pass: crime minor head, 24 MO flags, victim gender. Crime major
   is derived from the minor head. Its confidence is meaningful, so we route on it.
3. **System 2: IBM Granite (`granite-4-h-small` on watsonx.ai)**, only when Laya is below **40% confidence**
   (about 12% of FIRs). It returns strict JSON (crime type, methods, accused, victim, factual summary), which is
   validated, repaired once if needed, and **grounded**:
   - a name must appear in the FIR text;
   - a first name alone, or a persona the fraudster claimed ("Inspector Vikram Rathore"), is never evidence;
   - an alias counts only when the text says "alias X".
4. **Links and clusters.**
   - FIRs sharing a hard identifier or a resolved accused name/alias get an **evidence link**.
   - **NetworkX** connected components over FIR ↔ identifier edges form **repeat-offender clusters**. They are
     ranked by a transparent points formula: FIRs, stations, districts, loss, recency, senior-citizen victims,
     money trail.
   - Similar stories without shared evidence become **pattern links**. These are shown as weak leads and never
     used to flag anyone.
5. **Station briefs.** Facts are computed from the data (period vs previous period, rising crime types, methods,
   losses, active clusters, links to other stations). Granite writes the brief, and it is **accepted only if every
   number in it exists in the facts**; otherwise a template brief is used.
6. **IBM Bob as the investigator's interface.** Our MCP server exposes 12 tools. In the "FIR Analyst" custom mode,
   Bob answers questions like *"Which repeat-offender clusters touched Navrangpura in August?"* with FIR and
   cluster ids, never asserting guilt. `bob run` produces weekly briefs headlessly.
7. **Human in the loop.** Every link is labelled "investigation lead, requires human verification". Uncertain
   classifications go to a **review queue** where an officer confirms or corrects them, and each decision is
   audited.

## What makes it different from the naive approach
| Naive approach | CrimeFIR |
|---|---|
| Send every FIR to a big LLM and ask it to "find patterns" | The LLM sees one FIR at a time, only when needed (~12%), and never decides links |
| Keyword/regex classification | Calibrated decision model + LLM second opinion: **83% minor / 93% major head** on unseen FIRs |
| Similarity scores that link everything | Evidence-only clusters: **100% cluster precision, 0 decoys clustered** |
| Claims without measurement | Answer-key dataset with a dev/test split; metrics shown in the app |
| One process that dies without a GPU | Separate model service, GPU → CPU fallback, rules-only degraded mode |

## Key design decisions
- **Laya over Jev.** Both are "System 1" decision models. Laya is open-source, runs locally, is free, and is Indian.
  Jev is a paid cloud API on a waitlist, and FIR data should not leave the station by default.
- **Granite on watsonx.ai for the LLM tier.** It's an IBM model with a free Lite quota. Bobcoins pay only for Bob,
  not model APIs. Usage is low by design: the full 400-FIR pass used about 85k tokens.
- **A separate model service with adapters (`models.yaml`).** Models can be swapped without code changes, the core
  API stays light (no ML libraries), and GPU/CPU placement is automatic.
- **Thresholds tuned only on the dev split.** The Laya confidence threshold is 0.40. Per-MO-flag thresholds are
  set, and 6 unreliable flags are disabled rather than shown. Pattern-link similarity is 0.97.
- **SQLite (WAL) via SQLAlchemy.** Zero setup for judges; PostgreSQL is a one-line `DATABASE_URL` change.
- **No Docker.** It isn't required anywhere, and GPU passthrough in Docker on Windows is fragile. We provide native
  start scripts instead.
- **Synthetic but real-case-grounded data.** PS10 asks for mock FIRs, and real FIRs contain personal data. Every
  crime pattern is sourced from public reports.

## User experience
1. **Ingest:** drop a file of FIRs and watch each stage progress live. The upload returns immediately.
2. **Dashboard:** crime mix, stations, monthly trend, top flagged clusters.
3. **Case file:** the auto-drafted I.I.F.-II (major/minor head, who decided and how sure, methods, victim,
   accused), evidence highlighted in the story, and related FIRs with the reason ("same bank account 4025…
   written as … and …").
4. **Repeat offenders:** risk-ranked clusters, each with a graph, timeline, key identifiers, risk factors and
   suggested actions (freeze/trail requests, CDRs, ANPR, joint investigation).
5. **Station briefs** for the SHO, and **AI accuracy** with measured accuracy, who decided each FIR (Laya / Granite / rules), watsonx usage and model/GPU status.
6. **IBM Bob:** plain-English questions answered with FIR ids.

## Measured results (held-out test split: 305 FIRs never used for tuning)
| Output | Result |
|---|---|
| Crime major / minor head | **93.4% / 83.0%** (macro-F1 0.816). Laya: 80.4% on the 265 FIRs it accepted. Granite: 40/40 on escalated FIRs. |
| Hard evidence extraction | **100% precision, 100% recall, 100% correct roles** |
| Accused names | 88% found |
| Repeat-offender clusters | **100% precision**, 93.7% recall, 11/12 planted gangs recovered exactly, **0 decoys** clustered |
| MO flags | F1 0.64 (the weakest output) |
| Throughput (RTX 3050 laptop, 4 GB) | 400 FIRs in ~6 min; a 6-FIR live batch in 14 s including 2 LLM calls |
