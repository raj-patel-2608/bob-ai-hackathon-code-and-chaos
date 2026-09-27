# CrimeFIR mock FIR dataset

Synthetic FIRs in the NCRB I.I.F.-I layout, grounded in real reported crime patterns (see [SOURCES.md](SOURCES.md)). Statistics are in [DATASET_CARD.md](DATASET_CARD.md).

| File | What it is | Used by |
|---|---|---|
| `firs_main.txt` | 400 FIRs separated by `---`, text only | Upload through the UI/API (pipeline input) |
| `firs_main.jsonl`, `firs_main.csv` | Same FIRs, one `raw_text` per record | Alternative upload formats |
| `ground_truth.json` | Answer key: crime major/minor head, MO flags, victim profile, identifiers with roles, accused, planted cluster/decoy ids, dev/test split | **Evaluation only**. Never read by the pipeline. |
| `demo_live_batch.txt` + `demo_live_ground_truth.json` | 6 new FIRs, 3 of which attach to existing gangs | Live demo |
| `generator/` | `build.py` (deterministic, seed `20260927`), `validate.py` | Reproducing and checking the data |

## Design
- **No labels in the text.** Real FIRs contain no crime category or MO; the tool must infer them.
- **12 planted repeat-offender clusters (66 FIRs)** across 9 police stations in 3 districts. They are linked by shared phones, mule accounts, UPI IDs, handles, vehicles or accused aliases, each written in different formats (`98765 43210`, `+91-9876543210`, `09876543210`, …). 2 members are deliberately linkable only by pattern, not by evidence.
- **40 decoys**: same crime pattern and period as a cluster, but no shared evidence. They test that the system does not over-link.
- **294 background FIRs** across all 17 crime types, with seasonal trends (digital-arrest and task scams rising, snatching in the festive months, burglaries in summer vacations).
- Realistic noise: missing header fields, typos, Hinglish, varied amount formats, complainant mobile numbers in the header (which must **not** be treated as offender evidence).
- Splits: `dev` (~30%) for tuning prompts and thresholds, `test` (~70%) for reported metrics.

## Regenerate and check
```bash
python src/dataset/generator/build.py
python src/dataset/generator/validate.py
```
