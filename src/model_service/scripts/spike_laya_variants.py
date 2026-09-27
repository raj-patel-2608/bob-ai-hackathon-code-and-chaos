"""Phase-0 spike, round 2: prompt/checkpoint variants for Laya on the dev split."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
TAX = json.loads((SRC / "shared" / "taxonomy.json").read_text(encoding="utf-8"))

MO_QUESTIONS = {
    "impersonated_bank_official": "Did the caller or offender claim to be from a bank or card department?",
    "impersonated_police_or_agency": "Did the offender claim to be police, CBI, customs or a government officer?",
    "asked_otp_or_card_details": "Was the victim asked to share an OTP, PIN, CVV or card number?",
    "remote_access_app": "Was the victim made to install AnyDesk, QuickSupport, TeamViewer or a screen-sharing app?",
    "video_call_used": "Was there a video call?",
    "motorcycle_used": "Did the offenders come or flee on a motorcycle or bike?",
    "forced_entry": "Was a lock, door, window or grill broken to get inside?",
    "physical_violence": "Was the victim beaten, hit or physically hurt?",
}


def narrative(text: str) -> str:
    return text.split("First Information contents:", 1)[-1].strip()


def readable(options: dict) -> tuple[dict, dict]:
    """Criteria keyed by human-readable label; returns (criteria, label->id)."""
    crit, back = {}, {}
    for key, v in options.items():
        crit[v["label"]] = v["hint"]
        back[v["label"]] = key
    return crit, back


def run(agent, dev, variant: str):
    maj_crit, maj_back = readable(TAX["crime_major"])
    hits_major = hits_minor = 0
    mo = {f: [0, 0, 0] for f in MO_QUESTIONS}
    t0 = time.perf_counter()
    for text, gt in dev:
        state = narrative(text)
        if variant == "flat_readable":
            min_crit, min_back = readable(TAX["crime_minor"])
            q = {"major": {"type": "choice", "instructions": "What kind of crime is reported in this police "
                                                             "complaint?", "criteria": maj_crit},
                 "minor": {"type": "choice", "instructions": "What exact type of crime is reported in this police "
                                                             "complaint?", "criteria": min_crit}}
            q.update({f: {"type": "noul", "instructions": text_q} for f, text_q in MO_QUESTIONS.items()})
            a = agent.predict(state, q)["answers"]
            major, minor = maj_back[a["major"]["choice"]], min_back[a["minor"]["choice"]]
        else:  # hierarchical: major first, then minor restricted to that major
            q = {"major": {"type": "choice", "instructions": "What kind of crime is reported in this police "
                                                             "complaint?", "criteria": maj_crit}}
            q.update({f: {"type": "noul", "instructions": text_q} for f, text_q in MO_QUESTIONS.items()})
            a = agent.predict(state, q)["answers"]
            major = maj_back[a["major"]["choice"]]
            subset = {k: v for k, v in TAX["crime_minor"].items() if v["major"] == major}
            min_crit, min_back = readable(subset)
            if len(min_crit) == 1:
                minor = next(iter(min_back.values()))
            else:
                a2 = agent.predict(state, {"minor": {"type": "choice", "instructions": "What exact type of crime is "
                                                     "reported in this police complaint?", "criteria": min_crit}})
                minor = min_back[a2["answers"]["minor"]["choice"]]
        hits_major += major == gt["crime_major"]
        hits_minor += minor == gt["crime_minor"]
        for f in MO_QUESTIONS:
            pred, true = a[f]["noul"] >= 0.5, f in gt["mo_flags"]
            mo[f][0] += pred and true
            mo[f][1] += pred and not true
            mo[f][2] += (not pred) and true
    n = len(dev)
    ms = (time.perf_counter() - t0) / n * 1000
    f1s = []
    for f, (tp, fp, fn) in mo.items():
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    print(f"{variant:15} major {hits_major / n:.3f}  minor {hits_minor / n:.3f}  mean MO-F1 {sum(f1s) / len(f1s):.2f}"
          f"  {ms:.0f} ms/FIR")


def main() -> int:
    import laya
    texts = (SRC / "dataset" / "firs_main.txt").read_text(encoding="utf-8").strip().split("\n\n---\n\n")
    truth = json.loads((SRC / "dataset" / "ground_truth.json").read_text(encoding="utf-8"))["firs"]
    dev = [(t, g) for t, g in zip(texts, truth) if g["split"] == "dev"]
    for sub in (None, "typed-decisions"):
        agent = laya.load("convaiinnovations/laya", device="cuda", subfolder=sub)
        print(f"--- checkpoint: {sub or 'english base'}")
        for variant in ("flat_readable", "hierarchical"):
            run(agent, dev, variant)
        del agent
    return 0


if __name__ == "__main__":
    sys.exit(main())
