"""Builds presentation/slides.pdf (16:9) with matplotlib. Edit the text below and re-run:

    python presentation/build_slides.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "demo" / "screenshots"
OUT = ROOT / "presentation" / "slides.pdf"

BG, PANEL, TEXT, MUTED = "#0B1012", "#171E23", "#E9ECEC", "#8B979E"
AMBER, RED, BLUE, GREEN, PURPLE = "#D9A441", "#C1442E", "#4C7EA8", "#5C8A6B", "#8B6BB8"
W, H = 13.333, 7.5


def new_slide(title, kicker=None):
    fig = plt.figure(figsize=(W, H), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    if kicker:
        ax.text(0.6, H - 0.55, kicker.upper(), color=AMBER, fontsize=11, fontweight="bold")
    ax.text(0.6, H - 1.05, title, color=TEXT, fontsize=26, fontfamily="serif")
    ax.plot([0.6, W - 0.6], [H - 1.35, H - 1.35], color="#212A30", lw=1)
    ax.text(W - 0.6, 0.3, "CrimeFIR · Team Code & Chaos · IBM x NFSU Bob Hackathon · PS10", color=MUTED,
            fontsize=9, ha="right")
    return fig, ax


def box(ax, x, y, w, h, title, body="", color=BLUE, title_size=13, body_size=10.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                facecolor=PANEL, edgecolor=color, lw=1.6))
    ax.add_patch(FancyBboxPatch((x, y), 0.07, h, boxstyle="square,pad=0", facecolor=color, edgecolor=color))
    ax.text(x + 0.22, y + h - 0.3, title, color=TEXT, fontsize=title_size, fontweight="bold", va="top")
    if body:
        ax.text(x + 0.22, y + h - 0.72, body, color=MUTED if color != AMBER else TEXT, fontsize=body_size,
                va="top", linespacing=1.45)


def arrow(ax, x1, y1, x2, y2, label=None, color=MUTED):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, color=color, lw=1.4))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, label, color=MUTED, fontsize=8.5, ha="center")


def bullets(ax, x, y, items, size=13, gap=0.52, color=TEXT):
    for i, item in enumerate(items):
        ax.text(x, y - i * gap, "•  " + item, color=color, fontsize=size, va="top")


def image(fig, path, rect):
    ax = fig.add_axes(rect)
    ax.imshow(mpimg.imread(path))
    ax.axis("off")


def table(ax, x, y, rows, col_w, row_h=0.5, header_color=AMBER, size=11.5):
    for r, row in enumerate(rows):
        cx = x
        for c, cell in enumerate(row):
            color = header_color if r == 0 else (TEXT if c == 0 else GREEN if "%" in cell or "/" in cell else TEXT)
            ax.text(cx, y - r * row_h, cell, color=color, fontsize=size, va="top",
                    fontweight="bold" if r == 0 else "normal")
            cx += col_w[c]
        ax.plot([x, x + sum(col_w)], [y - r * row_h - row_h + 0.08] * 2, color="#212A30", lw=0.8)


def build():
    pages = []

    # 1 title ----------------------------------------------------------------
    fig, ax = plt.figure(figsize=(W, H), facecolor=BG), None
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    ax.text(0.9, 5.2, "CrimeFIR", color=TEXT, fontsize=64, fontfamily="serif")
    ax.text(0.9, 4.45, "FIR Intelligence & Crime Pattern Detector", color=AMBER, fontsize=24)
    ax.text(0.9, 3.55, "Auto-drafts the crime classification of every FIR, links FIRs across police stations and\n"
                       "districts by hard evidence, flags repeat-offender clusters and writes station crime briefs,\n"
                       "queried in plain English through IBM Bob.", color=MUTED, fontsize=14, va="top", linespacing=1.5)
    ax.text(0.9, 1.3, "Team Code & Chaos   ·   Track 4: AI & Predictive   ·   Problem Statement 10   ·   IBM x NFSU Bob Hackathon",
            color=TEXT, fontsize=12)
    ax.text(0.9, 0.85, "IBM Bob  ·  IBM Granite on watsonx.ai  ·  IBM Granite Embedding  ·  Laya  ·  NetworkX",
            color=MUTED, fontsize=11)
    pages.append(fig)

    # 2 problem ----------------------------------------------------------------
    fig, ax = new_slide("Crores of FIRs, no intelligence layer", "The problem")
    bullets(ax, 0.7, 5.7, [
        "UP Police CCTNS alone holds 3+ crore digitised FIRs, with no NLP layer. Pattern analysis is manual.",
        "Jamtara-style gangs reuse the same phones and mule accounts against victims in many districts.",
        "Each victim files at their own station; each FIR writes 98765 43210 / +91-9876543210 / 09876543210 differently.",
        "Crime type and method (NCRB I.I.F.-II) are filled in by hand, later; the FIR itself has no crime-type field.",
        "Result: inter-district links are never surfaced, and money in mule accounts is gone before anyone connects cases.",
    ], size=13.5, gap=0.62)
    box(ax, 0.7, 0.8, 3.8, 1.35, "Investigating officer", "cannot see their case is the 6th of a ring", RED)
    box(ax, 4.75, 0.8, 3.8, 1.35, "Station House Officer", "no timely picture of rising crime / active gangs", AMBER)
    box(ax, 8.8, 0.8, 3.8, 1.35, "Victims", "₹2,140 cr lost to digital-arrest scams alone (2024)", BLUE)
    pages.append(fig)

    # 3 solution ---------------------------------------------------------------
    fig, ax = new_slide("Evidence first, AI where it helps, a human decides", "Our solution")
    box(ax, 0.7, 3.6, 3.9, 2.4, "1  Rules: hard evidence",
        "phones (all Indian formats), bank\naccounts, UPI IDs, IMEIs, vehicles,\nhandles, with role: offender /\nproperty / complainant", GREEN)
    box(ax, 4.75, 3.6, 3.9, 2.4, "2  Laya: System 1 (local GPU)",
        "crime Major/Minor Head, 24 MO\nflags, victim gender in one pass,\nwith calibrated confidence\naccept if confidence >= 0.40", PURPLE)
    box(ax, 8.8, 3.6, 3.9, 2.4, "3  IBM Granite: System 2",
        "watsonx.ai granite-4-h-small, only\nfor ~12% low-confidence FIRs;\nstrict JSON, validated, names\nmust appear in the FIR", AMBER)
    rows = [["PS10 asks", "CrimeFIR delivers"],
            ["Categorise each FIR by crime type", "Auto-drafted NCRB I.I.F.-II (4 major, 17 minor heads)"],
            ["Extract accused, location, MO, victim profile", "Accused + aliases, place, 24 MO flags, victim, loss"],
            ["Detect repeat-offender signatures", "Evidence links + NetworkX clusters with risk score"],
            ["Station trend summary + flagged offender list", "Number-verified Granite brief + ranked clusters"]]
    table(ax, 0.7, 3.2, rows, [5.4, 6.8], row_h=0.48, size=11)
    pages.append(fig)

    # 4 architecture -----------------------------------------------------------
    fig, ax = new_slide("Architecture", "How it is built")
    box(ax, 0.5, 4.3, 2.3, 1.2, "Investigator / SHO", "browser", MUTED, 12, 9.5)
    box(ax, 0.5, 2.2, 2.3, 1.4, "IBM Bob", "IDE / Bob Shell\n'FIR Analyst' mode", AMBER, 12, 9.5)
    box(ax, 3.4, 4.3, 2.4, 1.2, "Next.js UI :3000", "8 pages", BLUE, 12, 9.5)
    box(ax, 3.4, 2.2, 2.4, 1.4, "MCP server", "12 tools over\nthe core API", AMBER, 12, 9.5)
    box(ax, 6.4, 2.2, 3.0, 3.3, "core-api :8000",
        "FastAPI, no ML libs\ningestion + rules\njob queue + worker\nlinks, NetworkX clusters\nstation facts & briefs\nevaluation", BLUE, 12, 9.5)
    box(ax, 6.4, 0.6, 3.0, 1.1, "SQLite (WAL)", "SQLAlchemy, Postgres-ready", MUTED, 12, 9.5)
    box(ax, 10.0, 2.2, 2.9, 3.3, "model-service :8100",
        "loads models once\nLaya  (GPU -> CPU)\nGranite Embedding\n  (GPU -> CPU)\nGranite on watsonx.ai\nmodels.yaml adapters", PURPLE, 12, 9.5)
    arrow(ax, 2.8, 4.9, 3.4, 4.9); arrow(ax, 2.8, 2.9, 3.4, 2.9, "MCP")
    arrow(ax, 5.8, 4.9, 6.4, 4.4, "REST"); arrow(ax, 5.8, 2.9, 6.4, 3.0, "REST")
    arrow(ax, 7.9, 2.2, 7.9, 1.7); arrow(ax, 9.4, 3.85, 10.0, 3.85, "/v1")
    ax.text(10.0, 1.6, "Fallbacks: GPU -> CPU per model;\nmodel service down -> rules + review;\nwatsonx down -> review queue / template",
            color=MUTED, fontsize=9.5, va="top")
    pages.append(fig)

    # 5 pipeline ---------------------------------------------------------------
    fig, ax = new_slide("What happens to one FIR", "Pipeline: which technology does what")
    steps = [("Upload", "file / paste / Bob\nreturns batch id\nimmediately", MUTED),
             ("1 extract", "rules\nevidence + roles,\namounts, accused,\naliases", GREEN),
             ("2 decide", "Laya (GPU)\ncrime type, MO,\nvictim gender,\nconfidence", PURPLE),
             ("3 enrich", "IBM Granite (watsonx)\nonly if conf < 0.40\nJSON, validated,\ngrounded", AMBER),
             ("4 embed", "Granite Embedding\nstory -> 384-d\nvector", PURPLE),
             ("Batch end", "evidence + pattern\nlinks, NetworkX\nclusters, risk", BLUE)]
    for i, (t, b, c) in enumerate(steps):
        x = 0.5 + i * 2.1
        box(ax, x, 3.3, 1.9, 2.35, t, b, c, 12, 9.5)
        if i:
            arrow(ax, x - 0.2, 4.45, x, 4.45)
    box(ax, 0.5, 0.8, 5.9, 1.9, "Outputs", "auto-drafted I.I.F.-II per FIR · related FIRs with reasons ·\n"
        "flagged repeat-offender clusters + graph + actions ·\nstation brief (Granite, numbers verified) · review queue", GREEN, 12, 10)
    box(ax, 6.7, 0.8, 6.1, 1.9, "Reliability", "DB-backed queue: leases, retries with backoff, crash\n"
        "recovery, duplicate detection · health checks · token budget\n(400 FIRs used ~85k tokens) · every stage records model + device", BLUE, 12, 10)
    pages.append(fig)

    # 6-7 demo -----------------------------------------------------------------
    for title, left, right in (("Case file: auto-drafted I.I.F.-II with evidence", "02-fir-auto-drafted-iif2.png",
                                "03-repeat-offender-cluster-graph.png"),
                               ("Station brief and measured quality", "04-station-brief-granite.png",
                                "05-model-quality.png")):
        fig, ax = new_slide(title, "Demo")
        image(fig, SHOTS / left, [0.03, 0.12, 0.47, 0.68])
        image(fig, SHOTS / right, [0.51, 0.12, 0.47, 0.68])
        pages.append(fig)

    # 8 results ----------------------------------------------------------------
    fig, ax = new_slide("Measured, not claimed", "Results on 305 unseen test FIRs")
    rows = [["Output", "Result"],
            ["Crime major / minor head", "93.4% / 83.0%  (macro-F1 0.816)"],
            ["Laya (accepted at >= 0.40) / Granite (escalated)", "80.4% on 265 FIRs / 40 of 40 correct"],
            ["Hard evidence extraction", "100% precision, 100% recall, 100% roles"],
            ["Repeat-offender clusters", "100% precision, 93.7% recall, 11/12 gangs, 0 decoys"],
            ["Accused names", "88% found"],
            ["MO flags (weakest output)", "F1 0.64, 6 unreliable flags disabled"],
            ["Team's first prototype, on its own 350-FIR file", "found 1 of 12 repeated phones; CrimeFIR finds 12/12"],
            ["Throughput, RTX 3050 laptop 4 GB", "400 FIRs ~6 min; live batch of 6 in 14 s"]]
    table(ax, 0.7, 5.7, rows, [6.2, 6.0], row_h=0.55, size=12.5)
    pages.append(fig)

    # 9 IBM technology ---------------------------------------------------------
    fig, ax = new_slide("IBM technology is load-bearing", "IBM Bob · watsonx.ai · Granite")
    box(ax, 0.7, 3.3, 3.9, 2.6, "IBM Bob", "MCP server: 12 tools (search FIRs,\nrelated FIRs, flagged clusters,\n"
        "station trends & briefs)\n'FIR Analyst' custom mode + rules\nbob run: headless weekly brief", AMBER)
    box(ax, 4.75, 3.3, 3.9, 2.6, "IBM Granite on watsonx.ai", "granite-4-h-small (eu-de)\nSystem-2 second opinion\n"
        "grounded JSON extraction\nstation brief prose, numbers\nverified against the data", AMBER)
    box(ax, 8.8, 3.3, 3.9, 2.6, "IBM Granite Embedding", "granite-embedding-30m-english\nlocal GPU, CPU fallback\n"
        "narrative vectors for\npattern-only leads", AMBER)
    bullets(ax, 0.7, 2.6, ["Investigator asks Bob: \"Which high-risk clusters touched Navrangpura this month, and what first?\"",
                           "Bob calls CrimeFIR tools and answers with FIR / cluster ids, never asserting guilt.",
                           "Bob Shell runs the weekly station brief headlessly: bob run --format json --max-cost 2."], size=12.5, gap=0.55)
    pages.append(fig)

    # 10 impact ------------------------------------------------------------------
    fig, ax = new_slide("Impact and next steps", "Beyond the hackathon")
    bullets(ax, 0.7, 5.7, [
        "Plugs onto existing FIR text: no change to how FIRs are written; outputs map to NCRB forms.",
        "Surfaces inter-district rings in minutes: faster freeze requests on mule accounts, joint investigations.",
        "Scale path: PostgreSQL + pgvector, model-service replicas, batched Laya on a GPU server.",
        "Next: authentication and roles, Indian-language FIRs (Laya multilingual), officer feedback to retrain thresholds.",
    ], size=13.5, gap=0.7)
    box(ax, 0.7, 0.8, 12.0, 1.6, "Honest limitations", "synthetic (real-case-grounded) data · names without surname are not\n"
        "provably one person · MO flags weakest · pattern links weak · no auth yet · all links are leads needing verification",
        RED, 13, 11)
    pages.append(fig)

    with PdfPages(OUT) as pdf:
        for fig in pages:
            pdf.savefig(fig, facecolor=BG)
            plt.close(fig)
    print(f"wrote {OUT} ({len(pages)} slides)")


if __name__ == "__main__":
    build()
