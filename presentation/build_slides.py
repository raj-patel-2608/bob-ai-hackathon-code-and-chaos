"""Builds presentation/slides.pdf (16:9) with matplotlib. Edit the text below and re-run:

    python presentation/build_slides.py

Visual style matches the web app: light "records system" look, navy header band, khaki rule, square panels.
Every claim here must match the code (see docs/architecture.md); keep it honest when editing.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "demo" / "screenshots"
OUT = ROOT / "presentation" / "slides.pdf"

BG, PANEL, INK, MUTED, RULE = "#F1F1EC", "#FFFFFF", "#161D29", "#5B6472", "#D2D5D2"
NAVY, KHAKI = "#112D4E", "#A47A2A"
RED, AMBER, GREEN, BLUE, PURPLE = "#B91C1C", "#B06800", "#166E3C", "#1D5EAA", "#5F3DC4"
W, H = 13.333, 7.5
_installed = {f.name for f in font_manager.fontManager.ttflist}
SANS = next((f for f in ("IBM Plex Sans", "Segoe UI", "Arial", "DejaVu Sans") if f in _installed), "DejaVu Sans")
MONO = next((f for f in ("Roboto Mono", "Consolas", "DejaVu Sans Mono") if f in _installed), "DejaVu Sans Mono")
plt.rcParams["font.family"] = SANS


def canvas():
    fig = plt.figure(figsize=(W, H), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
    return fig, ax


def new_slide(title, kicker=None):
    fig, ax = canvas()
    ax.add_patch(Rectangle((0, H - 1.05), W, 1.05, facecolor=NAVY, edgecolor="none"))
    ax.add_patch(Rectangle((0, H - 1.1), W, 0.05, facecolor=KHAKI, edgecolor="none"))
    if kicker:
        ax.text(0.6, H - 0.38, kicker.upper(), color="#C9D3E0", fontsize=10, fontfamily=MONO, va="center")
    ax.text(0.6, H - 0.74, title, color="white", fontsize=23, fontweight="bold", va="center")
    ax.text(W - 0.6, H - 0.55, "CRIMEFIR", color="white", fontsize=13, fontfamily=MONO, ha="right", va="center")
    ax.plot([0.6, W - 0.6], [0.55, 0.55], color=RULE, lw=0.8)
    ax.text(0.6, 0.3, "Team Code & Chaos · IBM x NFSU Bob Hackathon · Track 4 · PS10", color=MUTED, fontsize=9,
            fontfamily=MONO)
    return fig, ax


def box(ax, x, y, w, h, title, body="", color=BLUE, title_size=12.5, body_size=10.5, dashed=False, label=None):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=PANEL, edgecolor=color if dashed else RULE, lw=1.4 if dashed else 1,
                           linestyle=(0, (5, 3)) if dashed else "solid"))
    ax.add_patch(Rectangle((x, y), 0.06, h, facecolor=color, edgecolor="none"))
    ax.text(x + 0.2, y + h - 0.26, title, color=INK, fontsize=title_size, fontweight="bold", va="top")
    if label:
        ax.text(x + w - 0.12, y + h - 0.26, label, color=color, fontsize=8.5, fontfamily=MONO, ha="right", va="top",
                fontweight="bold")
    if body:
        ax.text(x + 0.2, y + h - 0.66, body, color=MUTED, fontsize=body_size, va="top", linespacing=1.45)


def arrow(ax, x1, y1, x2, y2, label=None, color=MUTED, dashed=False, lx=0, ly=0.13):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, color=color, lw=1.3,
                                 linestyle=(0, (5, 3)) if dashed else "solid"))
    if label:
        ax.text((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label, color=color, fontsize=8.5, ha="center",
                fontfamily=MONO)


def bullets(ax, x, y, items, size=13, gap=0.5, color=INK):
    for i, item in enumerate(items):
        ax.add_patch(Rectangle((x, y - i * gap - 0.2), 0.08, 0.08, facecolor=KHAKI, edgecolor="none"))
        ax.text(x + 0.25, y - i * gap, item, color=color, fontsize=size, va="top")


def image(fig, path, x, width, caption=None, top=0.83):
    """Places a screenshot `width` (figure fraction) wide, top-aligned, keeping its aspect ratio."""
    img = mpimg.imread(path)
    h = width * W * img.shape[0] / img.shape[1] / H
    rect = [x, top - h, width, h]
    ax = fig.add_axes(rect)
    ax.imshow(img)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(RULE)
    if caption:
        fig.text(rect[0], rect[1] - 0.035, caption, color=MUTED, fontsize=10)


def table(ax, x, y, rows, col_w, row_h=0.47, size=11.5):
    for r, row in enumerate(rows):
        if r == 0:
            ax.add_patch(Rectangle((x - 0.1, y - row_h + 0.08), sum(col_w), row_h, facecolor="#E6E7E2", edgecolor="none"))
        cx = x
        for c, cell in enumerate(row):
            ax.text(cx, y - r * row_h, cell, va="top", fontsize=10 if r == 0 else size,
                    color=INK if r == 0 or c == 0 else (GREEN if any(k in cell for k in ("%", "/", "0 decoys")) else INK),
                    fontweight="bold" if r == 0 else "normal", fontfamily=MONO if r == 0 else SANS)
            cx += col_w[c]
        ax.plot([x - 0.1, x - 0.1 + sum(col_w)], [y - r * row_h - row_h + 0.08] * 2, color=RULE, lw=0.8)


def build():
    pages = []

    # 1 title ----------------------------------------------------------------------------------------------------
    fig, ax = canvas()
    ax.add_patch(Rectangle((0, 2.2), W, 5.3, facecolor=NAVY, edgecolor="none"))
    ax.add_patch(Rectangle((0, 2.14), W, 0.07, facecolor=KHAKI, edgecolor="none"))
    ax.text(0.9, 5.6, "CRIMEFIR", color="white", fontsize=58, fontfamily=MONO, fontweight="bold")
    ax.text(0.9, 4.75, "FIR Intelligence & Crime Pattern Detector", color="#E3C88E", fontsize=24)
    ax.text(0.9, 4.1, "Reads raw FIR text, auto-drafts the NCRB crime classification, links FIRs across police stations\n"
                      "and districts by hard evidence, flags repeat-offender groups and writes station crime briefs.",
            color="#D7DEE8", fontsize=14, va="top", linespacing=1.5)
    ax.text(0.9, 1.5, "Team Code & Chaos  ·  Track 4: AI & Predictive  ·  Problem Statement 10  ·  IBM x NFSU Bob Hackathon",
            color=INK, fontsize=12.5)
    ax.text(0.9, 1.0, "IBM Granite on watsonx.ai  ·  IBM Granite Embedding  ·  Laya  ·  NetworkX  ·  MCP server for IBM Bob",
            color=MUTED, fontsize=11, fontfamily=MONO)
    pages.append(fig)

    # 2 problem --------------------------------------------------------------------------------------------------
    fig, ax = new_slide("Crores of FIRs, no intelligence layer", "The problem")
    bullets(ax, 0.7, 5.9, [
        "UP Police CCTNS alone holds 3+ crore digitised FIRs, with no NLP layer. Pattern analysis is manual.",
        "Jamtara-style gangs reuse the same phones and mule accounts against victims in many districts.",
        "Each victim files at their own station; every FIR writes 98765 43210 / +91-9876543210 / 09876543210 differently.",
        "Crime type and method (NCRB I.I.F.-II) are filled in by hand, later; the FIR itself has no crime-type field.",
        "Result: inter-district links are never surfaced; money in mule accounts is gone before anyone connects cases.",
    ], size=13.5, gap=0.55)
    box(ax, 0.7, 0.9, 3.8, 1.3, "Investigating officer", "cannot see their case is the 6th of a ring", RED)
    box(ax, 4.75, 0.9, 3.8, 1.3, "Station House Officer", "no timely picture of rising crime / active gangs", AMBER)
    box(ax, 8.8, 0.9, 3.8, 1.3, "Victims", "₹2,140 cr lost to digital-arrest scams alone (2024)", BLUE)
    pages.append(fig)

    # 3 solution -------------------------------------------------------------------------------------------------
    fig, ax = new_slide("Evidence first, AI where it helps, a human decides", "Our solution")
    box(ax, 0.7, 3.75, 3.9, 2.25, "1  Rules: hard evidence",
        "phones (all Indian formats), bank\naccounts, UPI IDs, IMEIs, vehicles,\nhandles, with role: offender /\n"
        "property / complainant", GREEN)
    box(ax, 4.75, 3.75, 3.9, 2.25, "2  Laya: System 1 (local GPU)",
        "crime type (17) → category (4),\n24 method flags, victim gender,\nwith calibrated confidence;\n"
        "accepted if confidence ≥ 0.40", PURPLE)
    box(ax, 8.8, 3.75, 3.9, 2.25, "3  IBM Granite: System 2",
        "granite-4-h-small on watsonx.ai,\nonly for ~13% unsure FIRs;\nstrict JSON, validated,\nnames must appear in the FIR", AMBER)
    arrow(ax, 4.6, 4.85, 4.75, 4.85); arrow(ax, 8.65, 4.85, 8.8, 4.85)
    table(ax, 0.8, 3.3, [["PS10 ASKS", "CRIMEFIR DELIVERS"],
                         ["Categorise each FIR by crime type", "Auto-drafted NCRB I.I.F.-II: 4 categories, 17 crime types"],
                         ["Extract accused, location, MO, victim profile", "Accused + aliases, place, 24 method flags, victim, loss"],
                         ["Detect repeat-offender signatures", "Evidence links + NetworkX groups with a transparent risk score"],
                         ["Station trend summary + flagged offender list", "Number-verified Granite brief + ranked repeat-offender groups"]],
          [5.4, 6.4], row_h=0.5, size=12)
    pages.append(fig)

    # 4 architecture ---------------------------------------------------------------------------------------------
    fig, ax = new_slide("Architecture: what is built and how it talks", "How it is built")
    box(ax, 0.5, 4.55, 2.1, 1.05, "Investigator / SHO", "web browser", MUTED, 11.5, 9.5)
    box(ax, 3.1, 4.3, 2.6, 1.55, "Web app  :3000", "Next.js · main interface\nupload, case files, groups,\ngraph, briefs, accuracy",
        BLUE, 11.5, 9.5, label="IN USE")
    box(ax, 6.3, 2.2, 3.0, 3.65, "core-api  :8000", "FastAPI, no ML libraries\ningestion + dedup\nrules extraction\n"
        "job queue + worker\nlinks, NetworkX groups\nstation facts & briefs\nevaluation", BLUE, 11.5, 9.5, label="IN USE")
    box(ax, 6.3, 0.8, 3.0, 1.0, "SQLite (WAL)", "var/crimefir.db + original uploads", MUTED, 11.5, 9.5)
    box(ax, 9.9, 3.25, 2.95, 2.6, "model-service  :8100", "loads the models once\nLaya (GPU → CPU)\nGranite Embedding\n  (GPU → CPU)\n"
        "models.yaml adapters", PURPLE, 11.5, 9.5, label="IN USE")
    box(ax, 9.9, 1.55, 2.95, 1.3, "IBM watsonx.ai", "granite-4-h-small (eu-de)\n2nd opinion + brief text", AMBER, 11.5, 9.5,
        label="IN USE")
    box(ax, 0.5, 2.1, 2.1, 1.35, "IBM Bob", "'FIR Analyst' mode\n(.bob/ config)", AMBER, 11.5, 9.5, dashed=True)
    box(ax, 3.1, 2.1, 2.6, 1.35, "MCP server", "12 tools over the API\nverified with an MCP client", AMBER, 11.5, 9.5,
        dashed=True, label="VERIFIED")
    arrow(ax, 2.6, 5.07, 3.1, 5.07)
    arrow(ax, 5.7, 5.07, 6.3, 5.07, "REST")
    arrow(ax, 7.8, 2.2, 7.8, 1.8)
    arrow(ax, 9.3, 4.55, 9.9, 4.55, "/v1")
    arrow(ax, 11.37, 3.25, 11.37, 2.85, "HTTPS", lx=0.45, ly=-0.05)
    arrow(ax, 1.55, 4.55, 1.55, 3.45, "optional", dashed=True, color=AMBER, lx=0.5)
    arrow(ax, 2.6, 2.77, 3.1, 2.77, "MCP", dashed=True, color=AMBER, ly=0.1)
    arrow(ax, 5.7, 2.95, 6.3, 3.3, "REST", color=AMBER, dashed=True)
    ax.text(0.5, 6.12, "Solid = in use and verified.   Dashed = implemented; the MCP server is verified end-to-end with an MCP "
                       "client (smoke_test.py), but a live IBM Bob session has not been done yet.",
            color=MUTED, fontsize=9.5, va="center")
    ax.text(0.5, 1.75, "Fallbacks:\nGPU → CPU per model\nmodel service down → rules + review\nwatsonx down → review / template",
            color=MUTED, fontsize=9, va="top", linespacing=1.4)
    pages.append(fig)

    # 5 pipeline -------------------------------------------------------------------------------------------------
    fig, ax = new_slide("What happens to one FIR", "Pipeline: which technology does what")
    steps = [("Upload", "file or paste\nsaved unchanged,\nduplicates skipped,\nreturns at once", MUTED),
             ("1 Extract", "rules\nevidence + roles,\namounts, accused,\naliases", GREEN),
             ("2 Decide", "Laya (GPU)\ncrime type, methods,\nvictim gender,\nconfidence", PURPLE),
             ("3 Enrich", "IBM Granite\nonly if conf < 0.40\nJSON, validated,\ngrounded", AMBER),
             ("4 Embed", "Granite Embedding\nstory → 384-number\nvector", PURPLE),
             ("Batch end", "evidence + story\nlinks, NetworkX\ngroups, risk", BLUE)]
    bw, gap = 1.86, 0.2
    for i, (t, b, c) in enumerate(steps):
        x = 0.55 + i * (bw + gap)
        box(ax, x, 3.35, bw, 2.55, t, b, c, 12, 9.8)
        if i < len(steps) - 1:
            arrow(ax, x + bw, 4.6, x + bw + gap, 4.6)
    box(ax, 0.55, 0.85, 6.0, 2.1, "Outputs", "auto-drafted I.I.F.-II per FIR · connected FIRs with reasons ·\n"
        "ranked repeat-offender groups + graph + actions ·\nstation brief (Granite, numbers verified) · officer review queue",
        GREEN, 12, 10.2)
    box(ax, 6.8, 0.85, 6.0, 2.1, "Reliability", "database-backed queue: leases, retries, crash recovery ·\n"
        "live progress, Stop, Delete · worker never blocks uploads ·\nwatsonx token budget · 30 + 7 + 3 automated tests",
        BLUE, 12, 10.2)
    pages.append(fig)

    # 6-8 screenshots --------------------------------------------------------------------------------------------
    for title, kicker, left, lcap, right, rcap in (
            ("What an investigator sees", "Demo", "01-dashboard.png", "Dashboard: groups to act on first",
             "04-fir-case-file-auto-drafted.png", "Case file: auto-drafted I.I.F.-II, evidence, connected FIRs"),
            ("Repeat offenders across stations", "Demo", "05-repeat-offender-group-timeline.png",
             "One group: first case → later cases sharing the evidence", "06-link-graph-network.png",
             "All 12 groups, coloured by shared evidence"),
            ("Station briefs and measured accuracy", "Demo", "07-station-brief-granite.png",
             "Brief written by IBM Granite, every number checked", "08-ai-accuracy.png",
             "Who decided each FIR, watsonx usage, accuracy")):
        fig, ax = new_slide(title, kicker)
        image(fig, SHOTS / left, 0.04, 0.45, lcap)
        image(fig, SHOTS / right, 0.51, 0.45, rcap)
        pages.append(fig)

    # 9 results --------------------------------------------------------------------------------------------------
    fig, ax = new_slide("Measured, not claimed", "Results on 305 unseen test FIRs")
    table(ax, 0.8, 5.95, [["OUTPUT", "RESULT"],
                          ["Crime category / crime type", "93.4% / 83.0%  (macro-F1 0.816)"],
                          ["Laya (accepted at ≥ 0.40) / IBM Granite (escalated)", "80.4% on 265 FIRs / 40 of 40 correct"],
                          ["Hard evidence extraction", "100% precision, 100% recall, 100% correct roles"],
                          ["Repeat-offender groups", "100% precision, 93.7% recall, 11/12 gangs, 0 decoys"],
                          ["Accused names", "88% found"],
                          ["Method flags (weakest output)", "F1 0.64; 6 unreliable flags switched off"],
                          ["Team's first prototype, same 350-FIR file", "found 1 of 12 repeated phones; CrimeFIR 12/12"],
                          ["Speed, RTX 3050 laptop (4 GB)", "400 FIRs in ~6–8 min; live batch of 6 in 14 s"]],
          [6.2, 5.6], row_h=0.55, size=12.5)
    pages.append(fig)

    # 10 IBM technology ------------------------------------------------------------------------------------------
    fig, ax = new_slide("IBM technology: where it is used", "IBM watsonx.ai · Granite · Bob")
    box(ax, 0.7, 3.2, 3.9, 2.75, "IBM Granite on watsonx.ai", "granite-4-h-small, Frankfurt (eu-de)\nused for exactly two things:\n"
        "1. second opinion when Laya is\n    < 40% sure (~13% of FIRs)\n2. station brief text, numbers verified",
        AMBER, label="IN USE")
    box(ax, 4.75, 3.2, 3.9, 2.75, "IBM Granite Embedding", "granite-embedding-30m-english\nlocal GPU, CPU fallback\n"
        "story vectors for weak\n'similar story' leads (never used\nto flag anyone)", AMBER, label="IN USE")
    box(ax, 8.8, 3.2, 3.9, 2.75, "IBM Bob via MCP", "MCP server: 12 tools (search FIRs,\nconnected FIRs, groups, station\n"
        "trends & briefs, ingest)\n.bob/ 'FIR Analyst' mode + rules\nlive Bob session: at the hackathon",
        AMBER, dashed=True, label="SERVER VERIFIED")
    bullets(ax, 0.7, 2.55, [
        "A full 400-FIR run used about 90k watsonx tokens; a monthly token budget stops calls before the quota runs out.",
        "The MCP server is proven the way Bob uses it: started over stdio, 12 tools listed, calls return live data.",
        "With Bob: “Which high-risk groups touched Navrangpura this month, and what first?” → answers with FIR / group ids.",
    ], size=12, gap=0.52)
    pages.append(fig)

    # 11 impact / limits -----------------------------------------------------------------------------------------
    fig, ax = new_slide("Impact, limits and next steps", "Beyond the hackathon")
    bullets(ax, 0.7, 5.95, [
        "Works on existing FIR text: no change to how FIRs are written; outputs map to the NCRB forms.",
        "Surfaces inter-district rings in minutes: faster freeze requests on mule accounts, joint investigations.",
        "Scale path: PostgreSQL + pgvector, incremental linking, model-service replicas, batched Laya on a GPU server.",
        "Next: run CrimeFIR inside IBM Bob, authentication and roles, Indian-language FIRs, fuzzy name matching.",
    ], size=13, gap=0.55)
    box(ax, 0.7, 0.9, 12.0, 1.85, "Honest limitations",
        "synthetic (real-case-grounded) data · names without a surname are not provably one person · method flags weakest ·\n"
        "story links weak · no authentication yet · IBM Bob not yet run live · every link is a lead that needs verification",
        RED, 12.5, 11)
    pages.append(fig)

    with PdfPages(OUT) as pdf:
        for f in pages:
            pdf.savefig(f, facecolor=f.get_facecolor())
            plt.close(f)
    print(f"wrote {OUT} ({len(pages)} slides, font {SANS} / {MONO})")


if __name__ == "__main__":
    build()
