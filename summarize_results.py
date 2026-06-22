#!/usr/bin/env python3
"""Aggregate + summarize workshop elicitation results (phase 1 and phase 2).

Reads a CSV in the `fetch_results.py` / `make_mock_results.py` schema (one row
per expert x failure_mode x technique, with round / group_id / personal_id) and
produces a per-cell (failure_mode x technique) summary.

Aggregation = the same PERT method used for the LLM experts in the talk:
    Step 1 (per expert):   PERT = (lower + 4 * point + upper) / 6
    Step 2 (across experts): Estimate = mean(PERT_i)  -> one value per cell

Two modes
---------
  --mode round1   Post-round-1 summary (no discussion yet). Reports the PERT
                  average per cell + spread, AND selects, per cell, the
                  discussion rationales (lowest / typical / highest by PERT),
                  and builds a slide deck:
                    * 1 overview slide: the 2x2 results matrix
                    * 1 slide per case: the selected rationales
                  -> summary_output/round1_results.pptx

  --mode phase2   Post-round-2 summary. Same PERT average on round-2 estimates,
                  PLUS convergence diagnostics vs round 1 (cross-expert spread
                  reduction and per-person revision).

  --method mixture   Optional: additionally attach a Monte-Carlo p05/p95 band.
                     The headline Estimate stays the PERT average.

estimate = % reduction in failure-mode success rate vs SFT baseline; HIGHER =
more effective. Negatives = the technique makes the failure mode WORSE.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

FM_LABEL = {"jailbreaking": "Jailbreaking", "deceptive_alignment": "Deceptive Alignment"}
TECH_LABEL = {"rlhf": "RLHF", "ai_debate": "AI Debate"}
FM_ORDER = ["jailbreaking", "deceptive_alignment"]
TECH_ORDER = ["rlhf", "ai_debate"]
NEEDED = ["failure_mode_id", "technique_id", "point_estimate",
          "lower_bound", "upper_bound", "round"]

# rationale is "substantive" enough to show if it clears these bars
MIN_RATIONALE_CHARS = 15
MIN_RATIONALE_WORDS = 3


# --------------------------------------------------------------------------- #
# Core PERT aggregation (matches the LLM-expert slide)
# --------------------------------------------------------------------------- #
def pert_score(point, lower, upper):
    """Per-expert PERT score: (lower + 4*point + upper) / 6."""
    return (lower + 4.0 * point + upper) / 6.0


def aggregate_cells(df, method="pert", lo=None, hi=100.0, n=8000, seed=42):
    """One row per (failure_mode, technique). Headline `estimate` = mean PERT."""
    rng = np.random.default_rng(seed)
    recs = []
    for (fm, tech), rows in df.groupby(["failure_mode_id", "technique_id"]):
        p = rows["pert"].to_numpy()
        pe = rows["point_estimate"].to_numpy()
        rec = dict(
            failure_mode=fm, technique=tech, n_experts=len(rows),
            estimate=p.mean(), pert_sd=p.std(ddof=0),
            pert_min=p.min(), pert_max=p.max(),
            best_min=pe.min(), best_max=pe.max(),
            mean_confidence=rows["confidence"].mean() if "confidence" in rows else np.nan,
        )
        if method == "mixture":
            mix = _cell_mixture(rows, lo, hi, n, rng)
            rec.update(mix_median=float(np.median(mix)),
                       mix_p05=float(np.percentile(mix, 5)),
                       mix_p95=float(np.percentile(mix, 95)))
        recs.append(rec)
    return pd.DataFrame(recs)


def pretty(df):
    out = df.copy()
    out["failure_mode"] = out.failure_mode.map(lambda x: FM_LABEL.get(x, x))
    out["technique"] = out.technique.map(lambda x: TECH_LABEL.get(x, x))
    return out


# --------------------------------------------------------------------------- #
# Discussion-rationale selection (part of the round-1 result)
# --------------------------------------------------------------------------- #
def _valid_rationale(s):
    if not isinstance(s, str):
        return False
    t = s.strip()
    return len(t) >= MIN_RATIONALE_CHARS and len(t.split()) >= MIN_RATIONALE_WORDS


def select_rationales(rows, mean_pert):
    """Pick lowest / typical / highest rationale (by PERT) for one cell.

    Filters out empty/junk rationales (with fallback to the next-nearest expert),
    dedupes to distinct experts, and anonymises (position labels only). Returns a
    list of 0-3 cards ordered [Lowest, Typical, Highest]."""
    pool = [r for r in rows.to_dict("records") if _valid_rationale(r.get("rationale"))]
    if not pool:
        return []
    asc = sorted(pool, key=lambda r: r["pert"])

    def card(r, label):
        return dict(label=label, best=r["point_estimate"], lo=r["lower_bound"],
                    hi=r["upper_bound"], conf=r.get("confidence"), pert=r["pert"],
                    rationale=str(r["rationale"]).strip())

    used, picks = set(), {}
    lo = asc[0]
    picks["Lowest"] = card(lo, "Lowest"); used.add(id(lo))
    for r in reversed(asc):                       # highest with a valid rationale
        if id(r) not in used:
            picks["Highest"] = card(r, "Highest"); used.add(id(r)); break
    remaining = [r for r in asc if id(r) not in used]
    if remaining:                                 # typical = closest to cell mean PERT
        typ = min(remaining, key=lambda r: abs(r["pert"] - mean_pert))
        picks["Typical"] = card(typ, "Typical")
    return [picks[k] for k in ("Lowest", "Typical", "Highest") if k in picks]


# --------------------------------------------------------------------------- #
# Optional Monte-Carlo band (mixture_pipeline.py construction)
# --------------------------------------------------------------------------- #
def _cell_mixture(rows, lo, hi, n, rng):
    from scipy.stats import beta as beta_dist
    from scipy.optimize import least_squares
    span = hi - lo
    eps = 1e-6
    s = lambda x: min(max((x - lo) / span, eps), 1 - eps)
    chunks = []
    for r in rows.itertuples():
        a_lo, c, b_hi = s(r.lower_bound), s(r.point_estimate), s(r.upper_bound)
        a_lo, b_hi = min(a_lo, b_hi), max(a_lo, b_hi)
        if b_hi - a_lo < 1e-3:
            a, b = c * 1e4, (1 - c) * 1e4
        else:
            pts = [(a_lo, 0.05), (c, 0.50), (b_hi, 0.95)]
            sd = (b_hi - a_lo) / 3.2897
            k = c * (1 - c) / max(sd * sd, 1e-6) - 1
            a0, b0 = max(c * k, 0.5), max((1 - c) * k, 0.5)
            sol = least_squares(
                lambda t: [beta_dist.cdf(x, *np.exp(t)) - p for x, p in pts],
                np.log([a0, b0]), xtol=1e-12, ftol=1e-12, max_nfev=5000)
            a, b = np.exp(sol.x)
        chunks.append(beta_dist.rvs(a, b, size=n, random_state=rng) * span + lo)
    return np.concatenate(chunks)


# --------------------------------------------------------------------------- #
# Slides (matches the LSAIR deck style)
# --------------------------------------------------------------------------- #
def build_slides(cells, selections, n_participants, path):
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
        from pptx.enum.shapes import MSO_SHAPE
    except ImportError:
        print("(python-pptx not installed -> skipping slides; pip install python-pptx)",
              file=sys.stderr)
        return None

    NAVY = RGBColor(0x15, 0x26, 0x4A); ORANGE = RGBColor(0xD9, 0x62, 0x2E)
    CARD = RGBColor(0xEE, 0xF1, 0xF6); GRAY = RGBColor(0x4A, 0x55, 0x68)
    LGRAY = RGBColor(0x70, 0x78, 0x86); WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    RED = RGBColor(0xC0, 0x39, 0x2B)
    SERIF, SANS = "Georgia", "Calibri"

    def mix(c1, c2, t):
        return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

    def tint(v):
        w = (255, 255, 255)
        if v < 0:
            return RGBColor(*mix(w, (0xD9, 0x53, 0x4F), 0.40))
        frac = max(0.0, min(1.0, v / 30.0))
        base = mix((0xE0, 0x6A, 0x55), (0x3C, 0x9A, 0x5F), frac)
        return RGBColor(*mix(w, base, 0.30))

    def num(x):
        return f"{x:.0f}" if abs(x - round(x)) < 0.05 else f"{x:.1f}"

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)

    def new_slide():
        return prs.slides.add_slide(prs.slide_layouts[6])

    def card(slide, x, y, w, h, fill, radius=0.04):
        b = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   Inches(x), Inches(y), Inches(w), Inches(h))
        b.fill.solid(); b.fill.fore_color.rgb = fill
        b.line.fill.background(); b.shadow.inherit = False
        try:
            b.adjustments[0] = radius
        except Exception:
            pass
        return b

    def txt(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = Inches(0.12)
        tf.margin_top = tf.margin_bottom = Inches(0.06)
        return tf

    def para(tf, runs, sb=4, sa=2, align=PP_ALIGN.LEFT, line=1.0, first=False):
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        p.alignment = align; p.space_before = Pt(sb); p.space_after = Pt(sa)
        p.line_spacing = line
        for text, size, color, bold, italic, font in runs:
            r = p.add_run(); r.text = text
            r.font.size = Pt(size); r.font.color.rgb = color
            r.font.bold = bold; r.font.italic = italic; r.font.name = font
        return p

    cset = {(r.failure_mode, r.technique): r for r in cells.itertuples()}

    # ---------------- Overview slide: 2x2 results matrix ----------------
    s = new_slide()
    t = txt(s, 0.55, 0.38, 12.2, 0.7)
    para(t, [("Round 1 — Results", 30, NAVY, True, False, SERIF)], first=True)
    sub = txt(s, 0.58, 1.16, 12.2, 0.5)
    para(sub, [(f"Mean PERT estimate across {n_participants} participants  ·  "
                "% reduction in failure-mode success vs SFT baseline  ·  higher = more effective",
                14, GRAY, False, True, SANS)], first=True)

    x0, y0, cw, ch, gap = 2.95, 2.45, 4.45, 1.95, 0.35
    for j, tech in enumerate(TECH_ORDER):                # column headers
        ht = txt(s, x0 + j * (cw + gap), y0 - 0.55, cw, 0.5, MSO_ANCHOR.MIDDLE)
        para(ht, [(TECH_LABEL.get(tech, tech), 17, NAVY, True, False, SANS)],
             align=PP_ALIGN.CENTER, first=True)
    for i, fm in enumerate(FM_ORDER):                    # row labels
        rl = txt(s, 0.45, y0 + i * (ch + gap), 2.35, ch, MSO_ANCHOR.MIDDLE)
        para(rl, [(FM_LABEL.get(fm, fm), 16, NAVY, True, False, SANS)],
             align=PP_ALIGN.RIGHT, first=True)
    for i, fm in enumerate(FM_ORDER):
        for j, tech in enumerate(TECH_ORDER):
            r = cset.get((fm, tech))
            if r is None:
                continue
            cx, cy = x0 + j * (cw + gap), y0 + i * (ch + gap)
            card(s, cx, cy, cw, ch, tint(r.estimate))
            cell = txt(s, cx, cy + 0.1, cw, ch - 0.2, MSO_ANCHOR.MIDDLE)
            para(cell, [(f"{num(r.estimate)}%", 38, NAVY, True, False, SERIF)],
                 align=PP_ALIGN.CENTER, first=True, sa=2)
            para(cell, [(f"best-guess range {num(r.best_min)}–{num(r.best_max)}%   ·   "
                         f"n={r.n_experts}   ·   SD {num(r.pert_sd)}",
                         11.5, GRAY, False, False, SANS)],
                 align=PP_ALIGN.CENTER, sb=2)

    # bottom takeaway
    foot = txt(s, 0.55, y0 + 2 * ch + gap + 0.15, 12.2, 0.5)
    bits = []
    for fm in FM_ORDER:
        sub_cells = [cset[(fm, te)] for te in TECH_ORDER if (fm, te) in cset]
        if sub_cells:
            best = max(sub_cells, key=lambda r: r.estimate)
            bits.append(f"{FM_LABEL.get(fm, fm)} → {TECH_LABEL.get(best.technique, best.technique)} "
                        f"({num(best.estimate)}%)")
    para(foot, [("Best technique per failure mode:  ", 12.5, ORANGE, True, False, SANS),
                ("    ".join(bits), 12.5, GRAY, False, False, SANS)], first=True)

    # ---------------- One slide per case: selected rationales ----------------
    LABEL_COLOR = {"Lowest": RED, "Typical": GRAY, "Highest": RGBColor(0x2E, 0x7D, 0x46)}
    order = sorted(cells.itertuples(), key=lambda r: r.pert_sd, reverse=True)  # most disagreement first
    for r in order:
        fm, tech = r.failure_mode, r.technique
        cards = selections.get((fm, tech), [])
        s = new_slide()
        ti = txt(s, 0.55, 0.38, 12.2, 0.7)
        para(ti, [(f"{FM_LABEL.get(fm, fm)}  ×  {TECH_LABEL.get(tech, tech)}",
                   28, NAVY, True, False, SERIF)], first=True)
        st = txt(s, 0.58, 1.12, 12.2, 0.5)
        para(st, [(f"Round-1 estimate ", 14, GRAY, False, False, SANS),
                  (f"{num(r.estimate)}%", 14, NAVY, True, False, SANS),
                  (f"   ·   best-guess range {num(r.best_min)}–{num(r.best_max)}%   ·   "
                   f"n={r.n_experts}   ·   spread (SD) {num(r.pert_sd)}", 14, GRAY, False, True, SANS)],
             first=True)

        if not cards:
            note = txt(s, 0.55, 3.0, 12.2, 1.0, MSO_ANCHOR.MIDDLE)
            para(note, [("No substantive rationales were provided for this cell.",
                         16, LGRAY, False, True, SANS)], align=PP_ALIGN.CENTER, first=True)
            continue

        m, gp = 0.55, 0.4
        cwid = (13.333 - 2 * m - gp * (len(cards) - 1)) / len(cards)
        cy, chh = 2.05, 4.85
        for k, c in enumerate(cards):
            cx = m + k * (cwid + gp)
            card(s, cx, cy, cwid, chh, CARD)
            head = txt(s, cx + 0.05, cy + 0.12, cwid - 0.1, 1.5)
            para(head, [(c["label"].upper(), 13, LABEL_COLOR.get(c["label"], ORANGE), True, False, SANS)],
                 first=True, sa=3)
            para(head, [(f"{num(c['best'])}%", 30, NAVY, True, False, SERIF)], sb=2, sa=1)
            conf = "—" if c["conf"] is None or (isinstance(c["conf"], float) and np.isnan(c["conf"])) \
                else f"{int(round(c['conf']))}/5"
            para(head, [(f"range {num(c['lo'])}–{num(c['hi'])}%   ·   confidence {conf}",
                         11, LGRAY, False, False, SANS)], sb=1)
            body = txt(s, cx + 0.05, cy + 1.7, cwid - 0.1, chh - 1.85)
            rtext = c["rationale"]
            if len(rtext) > 700:
                rtext = rtext[:699].rstrip() + "…"
            para(body, [(rtext, 12.5, GRAY, False, False, SANS)], first=True, line=1.12)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(path)
    return path


# --------------------------------------------------------------------------- #
# Modes
# --------------------------------------------------------------------------- #
def run_round1(df, args, outdir):
    sub = df[df["round"] == args.round1_label]
    if sub.empty:
        sys.exit(f"No rows with round == {args.round1_label!r}. "
                 f"Rounds present: {sorted(df['round'].dropna().unique())}")
    cells = aggregate_cells(sub, args.method, args.lo, args.hi, args.n, args.seed)

    # discussion rationales per cell (part of the round-1 result)
    selections, rat_rows = {}, []
    for r in cells.itertuples():
        rows = sub[(sub.failure_mode_id == r.failure_mode) & (sub.technique_id == r.technique)]
        picks = select_rationales(rows, r.estimate)
        selections[(r.failure_mode, r.technique)] = picks
        for c in picks:
            rat_rows.append(dict(failure_mode=r.failure_mode, technique=r.technique,
                                 selection=c["label"], best_guess=c["best"], lower=c["lo"],
                                 upper=c["hi"], confidence=c["conf"], pert=round(c["pert"], 2),
                                 rationale=c["rationale"]))

    order = ["failure_mode", "estimate"]
    cells = cells.sort_values(order, ascending=[True, False])
    cells.to_csv(outdir / "round1_cell_summary.csv", index=False)
    pd.DataFrame(rat_rows).to_csv(outdir / "round1_rationales.csv", index=False)

    cols = ["failure_mode", "technique", "n_experts", "estimate",
            "pert_sd", "pert_min", "pert_max", "mean_confidence"]
    if args.method == "mixture":
        cols[4:4] = ["mix_p05", "mix_p95"]
    print("=" * 92)
    print(f"ROUND 1 SUMMARY   estimate = mean PERT % risk reduction vs SFT (higher = better)"
          f"\n  PERT = (lower + 4*point + upper)/6, averaged over "
          f"{sub['personal_id'].nunique()} participants")
    print("=" * 92)
    pd.set_option("display.float_format", lambda v: f"{v:6.1f}")
    print(pretty(cells)[cols].to_string(index=False))

    print("\nBest / worst technique per failure mode (mean PERT):")
    for fm, g in cells.groupby("failure_mode"):
        g = g.sort_values("estimate", ascending=False)
        best, worst = g.iloc[0], g.iloc[-1]
        print(f"  {FM_LABEL.get(fm, fm):20s}: best {TECH_LABEL.get(best.technique, best.technique):9s} "
              f"({best.estimate:5.1f}%)   worst {TECH_LABEL.get(worst.technique, worst.technique):9s} "
              f"({worst.estimate:5.1f}%)")
    print(f"\nWrote {outdir/'round1_cell_summary.csv'} and {outdir/'round1_rationales.csv'}")

    if not args.no_slides:
        path = build_slides(cells, selections, sub["personal_id"].nunique(),
                            args.pptx or str(outdir / "round1_results.pptx"))
        if path:
            print(f"Wrote slides -> {path}  (1 overview + {len(cells)} case slides)")


def run_phase2(df, args, outdir):
    r1 = df[df["round"] == args.round1_label]
    r2 = df[df["round"] == args.round2_label]
    if r2.empty:
        sys.exit(f"No round-2 rows (round == {args.round2_label!r}). "
                 f"Rounds present: {sorted(df['round'].dropna().unique())}")

    cells = aggregate_cells(r2, args.method, args.lo, args.hi, args.n, args.seed)

    cell = ["failure_mode_id", "technique_id"]
    est1 = r1.groupby(cell).pert.mean()
    sd1 = r1.groupby(cell).pert.std(ddof=0)
    sd2 = r2.groupby(cell).pert.std(ddof=0)

    rev = pd.DataFrame()
    if "personal_id" in df and r1.personal_id.notna().any():
        keys = ["personal_id", "failure_mode_id", "technique_id"]
        paired = r1[keys + ["pert"]].merge(r2[keys + ["pert"]], on=keys, suffixes=("_r1", "_r2"))
        paired["abs_change"] = (paired.pert_r2 - paired.pert_r1).abs()
        paired["signed_change"] = paired.pert_r2 - paired.pert_r1
        rev = paired.groupby(cell).agg(n_paired=("abs_change", "size"),
                                       mean_abs_change=("abs_change", "mean"),
                                       mean_signed_change=("signed_change", "mean"))

    lk = lambda r, s: s.get((r.failure_mode, r.technique), np.nan)
    cells["r1_estimate"] = cells.apply(lambda r: lk(r, est1), axis=1)
    cells["delta_estimate"] = cells.estimate - cells.r1_estimate
    cells["sd_r1"] = cells.apply(lambda r: lk(r, sd1), axis=1)
    cells["sd_r2"] = cells.apply(lambda r: lk(r, sd2), axis=1)
    cells["spread_reduction"] = cells.sd_r1 - cells.sd_r2
    if not rev.empty:
        cells["n_paired"] = cells.apply(lambda r: lk(r, rev.n_paired), axis=1)
        cells["mean_abs_change"] = cells.apply(lambda r: lk(r, rev.mean_abs_change), axis=1)
        cells["mean_signed_change"] = cells.apply(lambda r: lk(r, rev.mean_signed_change), axis=1)

    cells = cells.sort_values(["failure_mode", "estimate"], ascending=[True, False])
    cells.to_csv(outdir / "phase2_cell_summary.csv", index=False)

    if "group_id" in r2 and r2.group_id.notna().any():
        grp = (r2.groupby(["group_id"] + cell).pert.mean().reset_index(name="group_estimate"))
        grp.to_csv(outdir / "phase2_group_estimates.csv", index=False)

    print("=" * 100)
    print("PHASE 2 SUMMARY   round-2 mean PERT + convergence vs round 1")
    print("=" * 100)
    pd.set_option("display.float_format", lambda v: f"{v:6.1f}")
    show = ["failure_mode", "technique", "n_experts", "estimate"]
    if args.method == "mixture":
        show += ["mix_p05", "mix_p95"]
    print("Round-2 aggregate:")
    print(pretty(cells)[show].rename(columns={"estimate": "r2_estimate"}).to_string(index=False))

    conv = ["failure_mode", "technique", "r1_estimate", "estimate", "delta_estimate",
            "sd_r1", "sd_r2", "spread_reduction"]
    if "mean_abs_change" in cells:
        conv += ["n_paired", "mean_abs_change", "mean_signed_change"]
    print("\nConvergence r1 -> r2  (delta_estimate = shift; spread_reduction>0 means experts "
          "moved closer;\n  mean_abs_change = avg individual revision, on PERT scores):")
    print(pretty(cells)[conv].rename(columns={"estimate": "r2_estimate"}).to_string(index=False))
    print(f"\nWrote {outdir/'phase2_cell_summary.csv'}"
          + (f" and {outdir/'phase2_group_estimates.csv'}"
             if (outdir / 'phase2_group_estimates.csv').exists() else ""))


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?", default=str(HERE / "results_mock.csv"),
                    help="input CSV (default: results_mock.csv)")
    ap.add_argument("--mode", choices=["round1", "phase2"], default="round1")
    ap.add_argument("--method", choices=["pert", "mixture"], default="pert",
                    help="pert = slide method (default); mixture = also attach a p05/p95 band")
    ap.add_argument("--lo", type=float, default=None, help="mixture support lower bound (auto)")
    ap.add_argument("--hi", type=float, default=100.0, help="mixture support upper bound (100)")
    ap.add_argument("--n", type=int, default=8000, help="mixture samples per expert")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--round1-label", default="1")
    ap.add_argument("--round2-label", default="2")
    ap.add_argument("--out", default=str(HERE / "summary_output"))
    ap.add_argument("--pptx", default=None, help="round-1 slide output path (default: <out>/round1_results.pptx)")
    ap.add_argument("--no-slides", action="store_true", help="skip slide generation")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    missing = [c for c in NEEDED if c not in df.columns]
    if missing:
        sys.exit(f"Input is missing required columns: {missing}")
    for c in ["point_estimate", "lower_bound", "upper_bound", "confidence"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["round"] = df["round"].astype("string").str.strip()
    before = len(df)
    df = df.dropna(subset=["point_estimate", "lower_bound", "upper_bound"]).copy()
    if len(df) < before:
        print(f"(dropped {before - len(df)} rows with missing estimate/bounds)", file=sys.stderr)
    df["pert"] = pert_score(df.point_estimate, df.lower_bound, df.upper_bound)

    if args.method == "mixture" and args.lo is None:
        import math
        data_min = min(df.point_estimate.min(), df.lower_bound.min())
        args.lo = float(min(0.0, math.floor(data_min) - 5)) if data_min < 0 else 0.0
        if data_min < 0:
            print(f"(negative estimates -> mixture support lower bound {args.lo:g}; --lo to override)",
                  file=sys.stderr)

    outdir = Path(args.out)
    outdir.mkdir(exist_ok=True)
    (run_round1 if args.mode == "round1" else run_phase2)(df, args, outdir)


if __name__ == "__main__":
    main()
