"""Measures the pipeline against the dataset answer key (src/dataset/ground_truth.json).

The answer key is only read here, never by the pipeline. FIRs are matched by
the SHA-256 of their text, so evaluation works whatever ids the system assigned.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SRC_DIR, get_settings
from ..db.models import ClusterMember, Entity, EvalRun, Fir, FirAnalysis, Link
from ..domain.enums import LinkKind
from ..extraction.accused import normalize_person
from ..extraction.fir_parser import split_batch

DATASET_DIR = SRC_DIR / "dataset"


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
            "tp": tp, "fp": fp, "fn": fn}


def load_truth(dataset_dir: Path = DATASET_DIR) -> dict[str, dict]:
    texts = split_batch((dataset_dir / "firs_main.txt").read_text(encoding="utf-8"), "firs_main.txt")
    truth = json.loads((dataset_dir / "ground_truth.json").read_text(encoding="utf-8"))["firs"]
    return {hashlib.sha256(t.strip().encode("utf-8")).hexdigest(): g for t, g in zip(texts, truth)}


def evaluate(session: Session, split: str = "test", dataset_dir: Path = DATASET_DIR) -> dict:
    truth_by_hash = load_truth(dataset_dir)
    firs = session.execute(select(Fir.id, Fir.text_sha256)).all()
    gt_of = {fid: truth_by_hash[h] for fid, h in firs if h in truth_by_hash}
    in_split = {fid for fid, g in gt_of.items() if split == "all" or g["split"] == split}
    if not in_split:
        return {"error": f"no FIRs from split '{split}' are loaded; upload src/dataset/firs_main.txt first"}

    analyses = {a.fir_id: a for a in session.scalars(select(FirAnalysis).where(FirAnalysis.fir_id.in_(in_split)))}
    # ---------------------------------------------------------------- crime type
    by_decider = defaultdict(lambda: [0, 0])
    minor_ok = major_ok = 0
    per_class = defaultdict(lambda: [0, 0, 0])        # tp, fp, fn
    for fid in in_split:
        g, a = gt_of[fid], analyses.get(fid)
        pred = a.crime_minor if a else None
        ok = pred == g["crime_minor"]
        minor_ok += ok
        major_ok += bool(a and a.crime_major == g["crime_major"])
        by_decider[(a.decided_by if a else "none")][0] += ok
        by_decider[(a.decided_by if a else "none")][1] += 1
        if ok:
            per_class[pred][0] += 1
        else:
            per_class[g["crime_minor"]][2] += 1
            if pred:
                per_class[pred][1] += 1
    n = len(in_split)
    macro_f1 = sum(_prf(*v)["f1"] for v in per_class.values()) / max(len(per_class), 1)

    # ---------------------------------------------------------------- MO flags
    mo_tp = mo_fp = mo_fn = 0
    for fid in in_split:
        pred = set((analyses.get(fid).mo_flags or {}) if analyses.get(fid) else set())
        want = set(gt_of[fid]["mo_flags"])
        mo_tp += len(pred & want); mo_fp += len(pred - want); mo_fn += len(want - pred)

    # ---------------------------------------------------------------- identifiers
    ents = session.execute(select(Entity.fir_id, Entity.type, Entity.value, Entity.role)
                           .where(Entity.fir_id.in_(in_split),
                                  Entity.type.in_(("phone", "bank_account", "upi_id", "imei", "vehicle",
                                                   "online_handle")))).all()
    got = defaultdict(dict)
    for fid, t, v, role in ents:
        got[fid][(t, v)] = role
    id_tp = id_fp = id_fn = role_ok = 0
    for fid in in_split:
        want = {(i["type"], i["value"]): i["role"] for i in gt_of[fid]["identifiers"]}
        for k, r in want.items():
            if k in got[fid]:
                id_tp += 1; role_ok += got[fid][k] == r
            else:
                id_fn += 1
        id_fp += sum(1 for k in got[fid] if k not in want)

    # ---------------------------------------------------------------- accused
    acc_total = acc_hit = acc_fp = 0
    for fid in in_split:
        g = gt_of[fid]["accused"]
        names = {x for p in ((analyses.get(fid).accused or []) if analyses.get(fid) else [])
                 if p.get("source") != "claimed" for x in (p.get("name"), p.get("alias")) if x}
        if g:
            acc_total += 1
            want = {normalize_person(g["canonical"])} | ({normalize_person(g["alias"])} if g["alias"] else set())
            acc_hit += bool(names & want)
        elif names:
            acc_fp += 1

    # ---------------------------------------------------------------- repeat-offender clusters (all loaded FIRs)
    pred_cluster = dict(session.execute(select(ClusterMember.fir_id, ClusterMember.cluster_id)).all())
    loaded = list(gt_of)
    true_pairs = set()
    for a, b in itertools.combinations(sorted(loaded), 2):
        ga, gb = gt_of[a], gt_of[b]
        if ga["cluster_id"] and ga["cluster_id"] == gb["cluster_id"] and ga["evidence_linkable"] \
                and gb["evidence_linkable"]:
            true_pairs.add((a, b))
    members = defaultdict(list)
    for fid, cid in pred_cluster.items():
        if fid in gt_of:            # FIRs outside the answer key (e.g. the live-demo batch) cannot be scored
            members[cid].append(fid)
    pred_pairs = {tuple(sorted(p)) for m in members.values() for p in itertools.combinations(m, 2)}
    tp = len(pred_pairs & true_pairs)
    gt_clusters = defaultdict(set)
    for fid, g in gt_of.items():
        if g["cluster_id"] and g["evidence_linkable"]:
            gt_clusters[g["cluster_id"]].add(fid)
    recovered = sum(1 for fids in gt_clusters.values()
                    if len({pred_cluster.get(f) for f in fids}) == 1 and None not in {pred_cluster.get(f) for f in fids}
                    and set(members[pred_cluster[next(iter(fids))]]) == fids)
    decoys_wrongly_linked = sum(1 for fid, g in gt_of.items() if g["decoy_of"] and fid in pred_cluster)
    pattern_links = session.scalars(select(Link).where(Link.kind == LinkKind.PATTERN)).all()
    pattern_same_cluster = sum(1 for l in pattern_links if gt_of.get(l.fir_a, {}).get("cluster_id")
                               and gt_of.get(l.fir_a, {}).get("cluster_id") == gt_of.get(l.fir_b, {}).get("cluster_id"))

    metrics = {
        "split": split, "firs_evaluated": n,
        "crime_minor_accuracy": round(minor_ok / n, 3), "crime_major_accuracy": round(major_ok / n, 3),
        "crime_minor_macro_f1": round(macro_f1, 3),
        "accuracy_by_decider": {k: {"accuracy": round(v[0] / v[1], 3), "firs": v[1]} for k, v in by_decider.items()},
        "escalated_to_llm": sum(1 for fid in in_split if analyses.get(fid) and analyses[fid].escalated),
        "mo_flags": _prf(mo_tp, mo_fp, mo_fn),
        "identifiers": {**_prf(id_tp, id_fp, id_fn), "role_accuracy": round(role_ok / id_tp, 3) if id_tp else None},
        "accused": {"with_accused": acc_total, "found": acc_hit,
                    "recall": round(acc_hit / acc_total, 3) if acc_total else None, "false_positive_firs": acc_fp},
        "clusters": {"pairwise": _prf(tp, len(pred_pairs - true_pairs), len(true_pairs - pred_pairs)),
                     "planted_clusters": len(gt_clusters), "recovered_exactly": recovered,
                     "predicted_clusters": len(members), "decoys_wrongly_clustered": decoys_wrongly_linked},
        "pattern_links": {"total": len(pattern_links), "within_same_planted_cluster": pattern_same_cluster},
        "note": "crime type / MO / identifiers / accused use the chosen split; clusters use every loaded FIR "
                "(clustering has no training step).",
    }
    s = get_settings()
    session.add(EvalRun(split=split, metrics=metrics,
                        settings={"decision_min_confidence": s.decision_min_confidence,
                                  "mo_flag_threshold": s.mo_flag_threshold,
                                  "soft_link_min_similarity": s.soft_link_min_similarity}))
    return metrics
