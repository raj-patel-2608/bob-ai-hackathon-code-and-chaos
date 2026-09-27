"""Calibrate decision thresholds on the DEV split only, then (optionally) re-apply them.

    python scripts/calibrate.py            # tune on dev, write src/shared/calibration.json
    python scripts/calibrate.py --apply    # also re-select MO flags for all FIRs and rebuild links

Laya's documentation notes its probabilities need calibration. Per MO flag we pick the probability
threshold with the best F1 on dev FIRs; flags that stay unreliable (F1 < MIN_F1) are disabled rather
than shown to investigators. The test split is never used here.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.engine import init_engine, session_scope  # noqa: E402
from app.db.models import Embedding, Fir, FirAnalysis  # noqa: E402
from app.pipeline.decisions import select_mo_flags  # noqa: E402
from app.services import intelligence  # noqa: E402
from app.services.evaluation import load_truth  # noqa: E402

MIN_F1 = 0.40
MIN_POSITIVES = 3
GRID = [round(x, 2) for x in np.arange(0.05, 0.96, 0.05)]


def f1(tp, fp, fn):
    return 2 * tp / (2 * tp + fp + fn) if tp else 0.0


def tune_mo(dev):
    flags = sorted({f for _, a in dev for f in (a.mo_probabilities or {})})
    thresholds, disabled, report = {}, [], {}
    for flag in flags:
        truth = [flag in g["mo_flags"] for g, _ in dev]
        probs = [(a.mo_probabilities or {}).get(flag, 0.0) for _, a in dev]
        positives = sum(truth)
        best = max(GRID, key=lambda t: (f1(*_counts(truth, probs, t)), t))
        score = f1(*_counts(truth, probs, best))
        report[flag] = {"threshold": best, "dev_f1": round(score, 3), "dev_positives": positives}
        if positives < MIN_POSITIVES or score < MIN_F1:
            disabled.append(flag)
        else:
            thresholds[flag] = best
    return thresholds, disabled, report


def _counts(truth, probs, t):
    tp = sum(1 for y, p in zip(truth, probs) if y and p >= t)
    fp = sum(1 for y, p in zip(truth, probs) if not y and p >= t)
    fn = sum(1 for y, p in zip(truth, probs) if y and p < t)
    return tp, fp, fn


def pattern_link_report(session, gt_of, dev_ids):
    """Precision of 'same planted offender' among same-crime-type dev pairs above each similarity."""
    rows = session.execute(select(Fir.id, FirAnalysis.crime_minor, Embedding.vector)
                           .join(FirAnalysis, FirAnalysis.fir_id == Fir.id)
                           .join(Embedding, Embedding.fir_id == Fir.id).where(Fir.id.in_(dev_ids))).all()
    pairs = []
    for a, b in itertools.combinations(rows, 2):
        if a.crime_minor != b.crime_minor:
            continue
        sim = float(np.frombuffer(a.vector, "<f4") @ np.frombuffer(b.vector, "<f4"))
        ca, cb = gt_of[a.id]["cluster_id"], gt_of[b.id]["cluster_id"]
        pairs.append((sim, bool(ca and ca == cb)))
    out = {}
    for t in (0.86, 0.90, 0.93, 0.95, 0.97):
        kept = [same for sim, same in pairs if sim >= t]
        out[str(t)] = {"pairs": len(kept), "same_offender": sum(kept),
                       "precision": round(sum(kept) / len(kept), 3) if kept else None}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    init_engine()
    s = get_settings()
    truth_by_hash = load_truth()
    with session_scope() as session:
        gt_of = {fid: truth_by_hash[h] for fid, h in session.execute(select(Fir.id, Fir.text_sha256))
                 if h in truth_by_hash}
        dev_ids = [fid for fid, g in gt_of.items() if g["split"] == "dev"]
        analyses = {a.fir_id: a for a in session.scalars(select(FirAnalysis).where(FirAnalysis.fir_id.in_(dev_ids)))}
        dev = [(gt_of[f], analyses[f]) for f in dev_ids if f in analyses and analyses[f].mo_probabilities]
        if not dev:
            print("no dev FIRs with MO probabilities: upload src/dataset/firs_main.txt and let it finish first")
            return 1
        thresholds, disabled, report = tune_mo(dev)
        calibration = {"created_at": datetime.now().isoformat(timespec="seconds"), "tuned_on": "dev split",
                       "dev_firs": len(dev), "min_f1": MIN_F1, "mo_thresholds": thresholds, "mo_disabled": disabled,
                       "mo_report": report, "pattern_links_dev": pattern_link_report(session, gt_of, dev_ids)}
    s.calibration_path.write_text(json.dumps(calibration, indent=2), encoding="utf-8")
    print(json.dumps({k: calibration[k] for k in ("dev_firs", "mo_disabled", "pattern_links_dev")}, indent=1))
    print(f"kept {len(thresholds)} MO flags, disabled {len(disabled)}; written to {s.calibration_path}")

    if args.apply:
        with session_scope() as session:
            for a in session.scalars(select(FirAnalysis).where(FirAnalysis.mo_probabilities.is_not(None),
                                                               FirAnalysis.decided_by == "laya")):
                a.mo_flags = select_mo_flags(a.mo_probabilities, s.mo_flag_threshold, calibration)
            intelligence.rebuild(session)
        print("re-applied MO thresholds to Laya-decided FIRs and rebuilt links/clusters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
