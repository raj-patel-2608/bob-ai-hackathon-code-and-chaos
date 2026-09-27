"""Validates the generated dataset against its answer key.

    python src/dataset/generator/validate.py

Checks:
  1. FIR keys are unique and texts and answer-key records line up
  2. every identifier in the answer key really appears in the FIR text
  3. no label or answer leaks into the FIR text
  4. dates are inside the dataset period and never in the future
  5. evidence-linkable members of each planted cluster are connected through shared identifiers,
     and decoys share no offender identifier with their cluster
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

DATASET = Path(__file__).resolve().parent.parent
LEAK_PATTERNS = [r"crime\s*category", r"\bcluster\b", r"\bdecoy\b", r"ideal example", r"modus operandi\s*:",
                 r"cyber\.\w+", r"property\.\w+", r"body\.\w+", r"economic\.\w+", r"ground.truth"]


def digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def appears(identifier: dict, text: str) -> bool:
    kind, value = identifier["type"], identifier["value"]
    if kind == "phone":
        return value[-10:] in digits(text)
    if kind in ("bank_account", "imei"):
        return value in digits(text)
    if kind == "vehicle":
        return value in re.sub(r"[\s\-]", "", text.upper())
    return value.lower() in text.lower()


def check(name: str, firs_file: str, truth_file: str, errors: list[str]) -> dict:
    texts = (DATASET / firs_file).read_text(encoding="utf-8").strip().split("\n\n---\n\n")
    truth = json.loads((DATASET / truth_file).read_text(encoding="utf-8"))["firs"]
    if len(texts) != len(truth):
        errors.append(f"{name}: {len(texts)} texts but {len(truth)} answer-key records")
    keys = [t["fir_key"] for t in truth]
    if len(set(keys)) != len(keys):
        errors.append(f"{name}: duplicate FIR keys")
    for text, rec in zip(texts, truth):
        fir_no = rec["fir_key"].rsplit("-", 1)[1]
        if f"FIR No.: {fir_no}/" not in text:
            errors.append(f"{rec['fir_key']}: text/answer-key misalignment")
        for ident in rec["identifiers"]:
            if not appears(ident, text):
                errors.append(f"{rec['fir_key']}: {ident['type']} {ident['value']} not found in text")
        if rec["accused"] and rec["accused"]["as_written"] and rec["accused"]["as_written"] not in text:
            errors.append(f"{rec['fir_key']}: accused '{rec['accused']['as_written']}' not in text")
        for pat in LEAK_PATTERNS:
            if re.search(pat, text, re.I):
                errors.append(f"{rec['fir_key']}: label leak matching /{pat}/")
        reg = date.fromisoformat(rec["registered_on"])
        if not (date(2026, 4, 1) <= reg <= date(2026, 9, 27)):
            errors.append(f"{rec['fir_key']}: registration date {reg} out of range")
    return {"texts": texts, "truth": truth}


def check_clusters(truth: list[dict], errors: list[str]) -> list[str]:
    report = []
    by_cluster = defaultdict(list)
    for rec in truth:
        if rec["cluster_id"]:
            by_cluster[rec["cluster_id"]].append(rec)

    def link_ids(rec):
        return {(i["type"], i["value"]) for i in rec["identifiers"] if i["role"] in ("offender", "property")} | (
            {("accused", rec["accused"]["canonical"])} if rec["accused"] and rec["accused"]["alias"] else set())

    for cid, members in sorted(by_cluster.items()):
        linkable = [m for m in members if m["evidence_linkable"]]
        # union-find over shared identifiers
        parent = {m["fir_key"]: m["fir_key"] for m in linkable}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        owner = {}
        for m in linkable:
            for ident in link_ids(m):
                if ident in owner:
                    parent[find(m["fir_key"])] = find(owner[ident])
                else:
                    owner[ident] = m["fir_key"]
        roots = {find(m["fir_key"]) for m in linkable}
        if len(roots) > 1:
            errors.append(f"{cid}: evidence-linkable members form {len(roots)} disconnected groups")
        cluster_ids = set(owner)
        for rec in truth:
            if rec["decoy_of"] == cid and link_ids(rec) & cluster_ids:
                errors.append(f"{rec['fir_key']}: decoy of {cid} shares an identifier with it")
        report.append(f"{cid}: {len(members)} FIRs, {len(linkable)} linkable, connected={len(roots) == 1}")
    return report


def main() -> int:
    errors: list[str] = []
    main_set = check("main", "firs_main.txt", "ground_truth.json", errors)
    live = check("live", "demo_live_batch.txt", "demo_live_ground_truth.json", errors)
    standalone = check("unrelated", "firs_unrelated.txt", "unrelated_ground_truth.json", errors)
    # standalone FIRs must share no identifier with any other FIR, and FIR keys must be unique across all files
    others = {(i["type"], i["value"]) for t in main_set["truth"] + live["truth"] for i in t["identifiers"]}
    for rec in standalone["truth"]:
        clash = {(i["type"], i["value"]) for i in rec["identifiers"]} & others
        if clash:
            errors.append(f"{rec['fir_key']}: standalone FIR shares identifiers {clash}")
        if rec["cluster_id"] or rec["decoy_of"]:
            errors.append(f"{rec['fir_key']}: standalone FIR has a cluster/decoy label")
    all_keys = [t["fir_key"] for t in main_set["truth"] + live["truth"] + standalone["truth"]]
    if len(all_keys) != len(set(all_keys)):
        errors.append("FIR keys repeat across the dataset files")
    for line in check_clusters(main_set["truth"], errors):
        print(line)
    if errors:
        print(f"\nFAILED with {len(errors)} problem(s):")
        for e in errors[:50]:
            print("  -", e)
        return 1
    print(f"\nOK: {len(main_set['truth'])} FIRs validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
