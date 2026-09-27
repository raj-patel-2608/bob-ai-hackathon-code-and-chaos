"""Phase-0 spike: can Laya classify crime type and MO flags from FIR narratives?

Runs on the dev split of the dataset only (the test split stays untouched).
    .venv/Scripts/python scripts/spike_laya.py [--device cuda|cpu] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
TAXONOMY = json.loads((SRC / "shared" / "taxonomy.json").read_text(encoding="utf-8"))
MO_TO_TEST = ["impersonated_bank_official", "impersonated_police_or_agency", "asked_otp_or_card_details",
              "remote_access_app", "video_call_used", "motorcycle_used", "forced_entry", "physical_violence"]


def narrative(text: str) -> str:
    return text.split("First Information contents:", 1)[-1].strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    import torch
    import laya

    texts = (SRC / "dataset" / "firs_main.txt").read_text(encoding="utf-8").strip().split("\n\n---\n\n")
    truth = json.loads((SRC / "dataset" / "ground_truth.json").read_text(encoding="utf-8"))["firs"]
    dev = [(t, g) for t, g in zip(texts, truth) if g["split"] == "dev"]
    if args.limit:
        dev = dev[:args.limit]

    t0 = time.perf_counter()
    agent = laya.load("convaiinnovations/laya", device=args.device) if "device" in laya.load.__code__.co_varnames \
        else laya.load("convaiinnovations/laya")
    if args.device == "cuda" and hasattr(agent, "to"):
        agent.to("cuda")
    load_s = time.perf_counter() - t0
    print(f"loaded in {load_s:.1f}s on {args.device}; type={type(agent).__name__}")

    majors = {k: v["hint"] for k, v in TAXONOMY["crime_major"].items()}
    minors = {k: v["hint"] for k, v in TAXONOMY["crime_minor"].items()}
    questions = {
        "crime_major": {"type": "choice", "instructions": "What kind of crime does this police complaint describe?",
                        "criteria": majors},
        "crime_minor": {"type": "choice", "instructions": "Which specific crime type does this police complaint "
                                                          "describe?", "criteria": minors},
    }
    for flag in MO_TO_TEST:
        questions[flag] = {"type": "noul", "instructions": f"In this complaint, {TAXONOMY['mo_flags'][flag]}?"}

    hits = Counter()
    mo_tp = Counter(); mo_fp = Counter(); mo_fn = Counter()
    confusion = Counter()
    latencies = []
    sample_printed = False
    for text, gt in dev:
        t1 = time.perf_counter()
        result = agent.predict(narrative(text), questions)
        latencies.append(time.perf_counter() - t1)
        ans = result["answers"]
        if not sample_printed:
            print("sample raw answer:", json.dumps(ans, default=str)[:900])
            sample_printed = True
        maj, mino = ans["crime_major"]["choice"], ans["crime_minor"]["choice"]
        hits["major"] += maj == gt["crime_major"]
        hits["minor"] += mino == gt["crime_minor"]
        if mino != gt["crime_minor"]:
            confusion[(gt["crime_minor"], mino)] += 1
        for flag in MO_TO_TEST:
            p = ans[flag]["noul"]
            pred, true = p >= 0.5, flag in gt["mo_flags"]
            mo_tp[flag] += pred and true
            mo_fp[flag] += pred and not true
            mo_fn[flag] += (not pred) and true

    n = len(dev)
    print(f"\nFIRs: {n}   mean latency per FIR (all {len(questions)} questions): "
          f"{sum(latencies) / n * 1000:.0f} ms   p95: {sorted(latencies)[int(n * 0.95) - 1] * 1000:.0f} ms")
    if args.device == "cuda":
        print(f"peak VRAM: {torch.cuda.max_memory_allocated() / 2**20:.0f} MiB")
    print(f"crime_major accuracy: {hits['major'] / n:.3f}")
    print(f"crime_minor accuracy: {hits['minor'] / n:.3f}")
    print("top confusions:", confusion.most_common(8))
    for flag in MO_TO_TEST:
        tp, fp, fn = mo_tp[flag], mo_fp[flag], mo_fn[flag]
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        print(f"  MO {flag:32} precision {prec:.2f} recall {rec:.2f} (tp {tp}, fp {fp}, fn {fn})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
