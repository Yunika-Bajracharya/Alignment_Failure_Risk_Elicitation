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
  --mode round1   Post-round-1 summary (no discussion yet). PERT average per cell
                  + spread, AND the discussion rationales (lowest / typical /
                  highest by PERT), plus a deck:
                    * overview slide: the 2x2 results matrix
                    * one slide per case: the selected rationales
                  -> summary_output/round1_results.pptx

  --mode phase2   Post-round-2 (post-discussion) summary. Same PERT average on
                  round-2 estimates, convergence diagnostics vs round 1, plus a deck:
                    * overview slide: final 2x2 matrix with change vs round 1
                    * one slide per case: round 1 -> round 2 spread comparison,
                      shift / revision stats, representative final rationale
                  -> summary_output/round2_results.pptx

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
    for r in reversed(asc):
        if id(r) not in used:
            picks["Highest"] = card(r, "Highest"); used.add(id(r)); break
    remaining = [r for r in asc if id(r) not in used]
    if remaining:
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
# Slides — shared deck factory (matches the LSAIR deck style)
# --------------------------------------------------------------------------- #
def _deck():
    """Build an empty 16:9 deck and a namespace of style helpers, or (None, None)
    if python-pptx is unavailable."""
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
        from pptx.enum.shapes import MSO_SHAPE
    except ImportError:
        return None, None
    from types import SimpleNamespace

    NAVY = RGBColor(0x15, 0x26, 0x4A); ORANGE = RGBColor(0xD9, 0x62, 0x2E)
    CARD = RGBColor(0xEE, 0xF1, 0xF6); GRAY = RGBColor(0x4A, 0x55, 0x68)
    LGRAY = RGBColor(0x70, 0x78, 0x86); WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    RED = RGBColor(0xC0, 0x39, 0x2B); GREEN = RGBColor(0x2E, 0x7D, 0x46)
    R1BAR = RGBColor(0xC9, 0xD4, 0xE3); R2BAR = RGBColor(0x2E, 0x4A, 0x7A)
    SERIF, SANS = "Georgia", "Calibri"

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

    def rect(slide, x, y, w, h, fill):
        b = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        b.fill.solid(); b.fill.fore_color.rgb = fill
        b.line.fill.background(); b.shadow.inherit = False
        return b

    def oval(slide, x, y, d, fill):
        b = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
        b.fill.solid(); b.fill.fore_color.rgb = fill
        b.line.color.rgb = WHITE; b.line.width = Pt(1); b.shadow.inherit = False
        return b

    def txt(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True; tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = Inches(0.1)
        tf.margin_top = tf.margin_bottom = Inches(0.05)
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
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return "—"
        return f"{x:.0f}" if abs(x - round(x)) < 0.05 else f"{x:.1f}"

    return prs, SimpleNamespace(**locals())


def _no_pptx():
    print("(python-pptx not installed -> skipping slides; pip install python-pptx)", file=sys.stderr)
    return None


# --------------------------------------------------------------------------- #
# Round-1 deck: overview matrix + per-case rationale slides
# --------------------------------------------------------------------------- #
def build_round1_slides(cells, selections, n_participants, path):
    prs, H = _deck()
    if prs is None:
        return _no_pptx()
    A = H.PP_ALIGN
    cset = {(r.failure_mode, r.technique): r for r in cells.itertuples()}

    # ---- Overview slide ----
    s = H.new_slide()
    H.para(H.txt(s, 0.55, 0.38, 12.2, 0.7),
           [("Round 1 — Results", 30, H.NAVY, True, False, H.SERIF)], first=True)
    H.para(H.txt(s, 0.58, 1.16, 12.2, 0.5),
           [(f"Mean PERT estimate across {n_participants} participants  ·  "
             "% reduction in failure-mode success vs SFT baseline  ·  higher = more effective",
             14, H.GRAY, False, True, H.SANS)], first=True)

    x0, y0, cw, ch, gap = 2.95, 2.45, 4.45, 1.95, 0.35
    for j, tech in enumerate(TECH_ORDER):
        H.para(H.txt(s, x0 + j * (cw + gap), y0 - 0.55, cw, 0.5, H.MSO_ANCHOR.MIDDLE),
               [(TECH_LABEL.get(tech, tech), 17, H.NAVY, True, False, H.SANS)], align=A.CENTER, first=True)
    for i, fm in enumerate(FM_ORDER):
        H.para(H.txt(s, 0.45, y0 + i * (ch + gap), 2.35, ch, H.MSO_ANCHOR.MIDDLE),
               [(FM_LABEL.get(fm, fm), 16, H.NAVY, True, False, H.SANS)], align=A.RIGHT, first=True)
    for i, fm in enumerate(FM_ORDER):
        for j, tech in enumerate(TECH_ORDER):
            r = cset.get((fm, tech))
            if r is None:
                continue
            cx, cy = x0 + j * (cw + gap), y0 + i * (ch + gap)
            H.card(s, cx, cy, cw, ch, H.tint(r.estimate))
            cell = H.txt(s, cx, cy + 0.1, cw, ch - 0.2, H.MSO_ANCHOR.MIDDLE)
            H.para(cell, [(f"{H.num(r.estimate)}%", 38, H.NAVY, True, False, H.SERIF)],
                   align=A.CENTER, first=True, sa=2)
            H.para(cell, [(f"best-guess range {H.num(r.best_min)}–{H.num(r.best_max)}%   ·   "
                           f"n={r.n_experts}   ·   SD {H.num(r.pert_sd)}", 11.5, H.GRAY, False, False, H.SANS)],
                   align=A.CENTER, sb=2)

    bits = []
    for fm in FM_ORDER:
        sub = [cset[(fm, te)] for te in TECH_ORDER if (fm, te) in cset]
        if sub:
            best = max(sub, key=lambda r: r.estimate)
            bits.append(f"{FM_LABEL.get(fm, fm)} → {TECH_LABEL.get(best.technique, best.technique)} "
                        f"({H.num(best.estimate)}%)")
    H.para(H.txt(s, 0.55, y0 + 2 * ch + gap + 0.15, 12.2, 0.5),
           [("Best technique per failure mode:  ", 12.5, H.ORANGE, True, False, H.SANS),
            ("    ".join(bits), 12.5, H.GRAY, False, False, H.SANS)], first=True)

    # ---- Per-case rationale slides (most disagreement first) ----
    LABEL_COLOR = {"Lowest": H.RED, "Typical": H.GRAY, "Highest": H.GREEN}
    for r in sorted(cells.itertuples(), key=lambda r: r.pert_sd, reverse=True):
        fm, tech = r.failure_mode, r.technique
        cards = selections.get((fm, tech), [])
        s = H.new_slide()
        H.para(H.txt(s, 0.55, 0.38, 12.2, 0.7),
               [(f"{FM_LABEL.get(fm, fm)}  ×  {TECH_LABEL.get(tech, tech)}", 28, H.NAVY, True, False, H.SERIF)],
               first=True)
        H.para(H.txt(s, 0.58, 1.12, 12.2, 0.5),
               [("Round-1 estimate ", 14, H.GRAY, False, False, H.SANS),
                (f"{H.num(r.estimate)}%", 14, H.NAVY, True, False, H.SANS),
                (f"   ·   best-guess range {H.num(r.best_min)}–{H.num(r.best_max)}%   ·   "
                 f"n={r.n_experts}   ·   spread (SD) {H.num(r.pert_sd)}", 14, H.GRAY, False, True, H.SANS)],
               first=True)

        if not cards:
            H.para(H.txt(s, 0.55, 3.0, 12.2, 1.0, H.MSO_ANCHOR.MIDDLE),
                   [("No substantive rationales were provided for this cell.", 16, H.LGRAY, False, True, H.SANS)],
                   align=A.CENTER, first=True)
            continue

        m, gp = 0.55, 0.4
        cwid = (13.333 - 2 * m - gp * (len(cards) - 1)) / len(cards)
        cy, chh = 2.05, 4.85
        for k, c in enumerate(cards):
            cx = m + k * (cwid + gp)
            H.card(s, cx, cy, cwid, chh, H.CARD)
            head = H.txt(s, cx + 0.05, cy + 0.12, cwid - 0.1, 1.5)
            H.para(head, [(c["label"].upper(), 13, LABEL_COLOR.get(c["label"], H.ORANGE), True, False, H.SANS)],
                   first=True, sa=3)
            H.para(head, [(f"{H.num(c['best'])}%", 30, H.NAVY, True, False, H.SERIF)], sb=2, sa=1)
            conf = "—" if c["conf"] is None or (isinstance(c["conf"], float) and np.isnan(c["conf"])) \
                else f"{int(round(c['conf']))}/5"
            H.para(head, [(f"range {H.num(c['lo'])}–{H.num(c['hi'])}%   ·   confidence {conf}",
                           11, H.LGRAY, False, False, H.SANS)], sb=1)
            body = H.txt(s, cx + 0.05, cy + 1.7, cwid - 0.1, chh - 1.85)
            rtext = c["rationale"]
            if len(rtext) > 700:
                rtext = rtext[:699].rstrip() + "…"
            H.para(body, [(rtext, 12.5, H.GRAY, False, False, H.SANS)], first=True, line=1.12)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(path)
    return path


# --------------------------------------------------------------------------- #
# Round-2 deck: final matrix + per-case convergence slides
# --------------------------------------------------------------------------- #
def _spread_chart(s, H, x, y, w, est1, sd1, est2, sd2):
    """Two horizontal SD bars (Round 1 vs Round 2) on a shared axis — shows the
    distribution narrowing and shifting after discussion."""
    A = H.PP_ALIGN
    sd1 = 0.0 if sd1 is None or np.isnan(sd1) else sd1
    sd2 = 0.0 if sd2 is None or np.isnan(sd2) else sd2
    vals = [est1 - sd1, est1 + sd1, est2 - sd2, est2 + sd2]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-6:
        hi = lo + 1
    pad = 0.10 * (hi - lo) + 1
    lo, hi = lo - pad, hi + pad
    mp = lambda v: x + (v - lo) / (hi - lo) * w
    y_r1, y_r2, y_axis, barh = y, y + 0.95, y + 1.85, 0.30

    if lo < 0 < hi:                                   # 0% reference line
        H.rect(s, mp(0) - 0.006, y - 0.28, 0.012, (y_axis - (y - 0.28)), H.RGBColor(0xCF, 0xD6, 0xDF))

    for yc, est, sd, col in [(y_r1, est1, sd1, H.R1BAR), (y_r2, est2, sd2, H.R2BAR)]:
        bx0, bx1 = mp(est - sd), mp(est + sd)
        H.rect(s, bx0, yc, max(bx1 - bx0, 0.04), barh, col)
        H.oval(s, mp(est) - 0.08, yc + barh / 2 - 0.08, 0.16, H.NAVY)
        H.para(H.txt(s, mp(est) - 0.7, yc - 0.36, 1.4, 0.32),
               [(f"{H.num(est)}%", 13, H.NAVY, True, False, H.SANS)], align=A.CENTER, first=True)

    for name, sd, yc in [("Round 1", sd1, y_r1), ("Round 2", sd2, y_r2)]:
        H.para(H.txt(s, x - 1.75, yc - 0.02, 1.65, 0.4, H.MSO_ANCHOR.MIDDLE),
               [(name, 12, H.GRAY, True, False, H.SANS), (f"  SD {H.num(sd)}", 10, H.LGRAY, False, True, H.SANS)],
               align=A.RIGHT, first=True)

    H.rect(s, x, y_axis, w, 0.014, H.RGBColor(0xB8, 0xC0, 0xCC))
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        H.para(H.txt(s, mp(v) - 0.45, y_axis + 0.04, 0.9, 0.3),
               [(f"{H.num(v)}%", 9, H.LGRAY, False, False, H.SANS)], align=A.CENTER, first=True)


def build_round2_slides(cells, selections, n_participants, path):
    prs, H = _deck()
    if prs is None:
        return _no_pptx()
    A = H.PP_ALIGN
    cset = {(r.failure_mode, r.technique): r for r in cells.itertuples()}
    get = lambda r, name, d=np.nan: getattr(r, name, d)

    # ---- Overview slide: final matrix + change vs round 1 ----
    s = H.new_slide()
    H.para(H.txt(s, 0.55, 0.38, 12.2, 0.7),
           [("Round 2 — Final Results", 30, H.NAVY, True, False, H.SERIF)], first=True)
    H.para(H.txt(s, 0.58, 1.16, 12.2, 0.5),
           [(f"After discussion  ·  mean PERT across {n_participants} participants  ·  "
             "change vs round 1 shown below each cell", 14, H.GRAY, False, True, H.SANS)], first=True)

    x0, y0, cw, ch, gap = 2.95, 2.45, 4.45, 1.95, 0.35
    for j, tech in enumerate(TECH_ORDER):
        H.para(H.txt(s, x0 + j * (cw + gap), y0 - 0.55, cw, 0.5, H.MSO_ANCHOR.MIDDLE),
               [(TECH_LABEL.get(tech, tech), 17, H.NAVY, True, False, H.SANS)], align=A.CENTER, first=True)
    for i, fm in enumerate(FM_ORDER):
        H.para(H.txt(s, 0.45, y0 + i * (ch + gap), 2.35, ch, H.MSO_ANCHOR.MIDDLE),
               [(FM_LABEL.get(fm, fm), 16, H.NAVY, True, False, H.SANS)], align=A.RIGHT, first=True)
    for i, fm in enumerate(FM_ORDER):
        for j, tech in enumerate(TECH_ORDER):
            r = cset.get((fm, tech))
            if r is None:
                continue
            cx, cy = x0 + j * (cw + gap), y0 + i * (ch + gap)
            H.card(s, cx, cy, cw, ch, H.tint(r.estimate))
            cell = H.txt(s, cx, cy + 0.1, cw, ch - 0.2, H.MSO_ANCHOR.MIDDLE)
            H.para(cell, [(f"{H.num(r.estimate)}%", 36, H.NAVY, True, False, H.SERIF)],
                   align=A.CENTER, first=True, sa=2)
            d = get(r, "delta_estimate")
            H.para(cell, [(f"R1 {H.num(get(r, 'r1_estimate'))}% → {H.num(r.estimate)}%   "
                           f"(Δ{d:+.1f})" if not np.isnan(d) else f"R1 → {H.num(r.estimate)}%",
                           11.5, H.GRAY, False, False, H.SANS)], align=A.CENTER, sb=2, sa=0)
            H.para(cell, [(f"spread SD {H.num(get(r, 'sd_r1'))} → {H.num(get(r, 'sd_r2'))}   ·   "
                           f"n={r.n_experts}", 11, H.LGRAY, False, False, H.SANS)], align=A.CENTER, sb=1)

    converged = int(sum(1 for r in cells.itertuples()
                        if not np.isnan(get(r, "spread_reduction")) and get(r, "spread_reduction") > 0))
    bits = []
    for fm in FM_ORDER:
        sub = [cset[(fm, te)] for te in TECH_ORDER if (fm, te) in cset]
        if sub:
            best = max(sub, key=lambda r: r.estimate)
            bits.append(f"{FM_LABEL.get(fm, fm)} → {TECH_LABEL.get(best.technique, best.technique)} "
                        f"({H.num(best.estimate)}%)")
    H.para(H.txt(s, 0.55, y0 + 2 * ch + gap + 0.12, 12.2, 0.6),
           [("Best technique per failure mode:  ", 12.5, H.ORANGE, True, False, H.SANS),
            ("    ".join(bits), 12.5, H.GRAY, False, False, H.SANS)], first=True)
    H.para(H.txt(s, 0.55, y0 + 2 * ch + gap + 0.42, 12.2, 0.4),
           [(f"Spread narrowed in {converged}/{len(cells)} cells after discussion — experts converged.",
             12, H.GREEN, False, True, H.SANS)], first=True)

    # ---- Per-case convergence slides (most remaining disagreement first) ----
    order = sorted(cells.itertuples(),
                   key=lambda r: (-1 if np.isnan(get(r, "sd_r2")) else get(r, "sd_r2")), reverse=True)
    for r in order:
        fm, tech = r.failure_mode, r.technique
        s = H.new_slide()
        H.para(H.txt(s, 0.55, 0.38, 12.2, 0.7),
               [(f"{FM_LABEL.get(fm, fm)}  ×  {TECH_LABEL.get(tech, tech)}", 28, H.NAVY, True, False, H.SERIF)],
               first=True)
        npr = get(r, "n_paired")
        H.para(H.txt(s, 0.58, 1.12, 12.2, 0.5),
               [("How estimates moved after discussion", 14, H.GRAY, False, True, H.SANS),
                (f"   ·   {int(npr)} experts paired across rounds" if not np.isnan(npr) else "",
                 14, H.LGRAY, False, True, H.SANS)], first=True)

        _spread_chart(s, H, x=2.5, y=2.35, w=9.0,
                      est1=get(r, "r1_estimate"), sd1=get(r, "sd_r1"),
                      est2=r.estimate, sd2=get(r, "sd_r2"))

        # stat chips
        d = get(r, "delta_estimate"); sr = get(r, "spread_reduction")
        mac = get(r, "mean_abs_change"); msc = get(r, "mean_signed_change")
        chips = [
            ("SHIFT IN ESTIMATE", f"{d:+.1f} pts" if not np.isnan(d) else "—"),
            ("CONVERGENCE (SD)", f"{H.num(get(r, 'sd_r1'))} → {H.num(get(r, 'sd_r2'))}"
             + (f"   (−{H.num(sr)})" if not np.isnan(sr) else "")),
            ("AVG INDIVIDUAL REVISION", (f"{H.num(mac)} pts" if not np.isnan(mac) else "—")
             + (f"   (net {msc:+.1f})" if not np.isnan(msc) else "")),
        ]
        m, gp, cy, chh = 0.55, 0.4, 4.7, 0.95
        cwid = (13.333 - 2 * m - gp * (len(chips) - 1)) / len(chips)
        for k, (lab, val) in enumerate(chips):
            cx = m + k * (cwid + gp)
            H.card(s, cx, cy, cwid, chh, H.CARD)
            tf = H.txt(s, cx + 0.1, cy + 0.08, cwid - 0.2, chh - 0.16)
            H.para(tf, [(lab, 10.5, H.ORANGE, True, False, H.SANS)], first=True, sa=3)
            H.para(tf, [(val, 17, H.NAVY, True, False, H.SANS)], sb=1)

        # representative post-discussion rationale (the round-2 "typical")
        picks = selections.get((fm, tech), [])
        typ = next((c for c in picks if c["label"] == "Typical"), picks[0] if picks else None)
        if typ:
            ry = cy + chh + 0.25
            H.card(s, m, ry, 13.333 - 2 * m, 1.15, H.CARD)
            tf = H.txt(s, m + 0.12, ry + 0.08, 13.333 - 2 * m - 0.24, 1.0)
            H.para(tf, [("REPRESENTATIVE POST-DISCUSSION RATIONALE", 10.5, H.ORANGE, True, False, H.SANS)],
                   first=True, sa=2)
            rtext = typ["rationale"]
            if len(rtext) > 320:
                rtext = rtext[:319].rstrip() + "…"
            H.para(tf, [(rtext, 12, H.GRAY, False, False, H.SANS)], sb=1, line=1.1)

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

    cells = cells.sort_values(["failure_mode", "estimate"], ascending=[True, False])
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
        path = build_round1_slides(cells, selections, sub["personal_id"].nunique(),
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

    # representative round-2 rationale per cell (post-discussion reasoning)
    selections = {}
    for r in cells.itertuples():
        rows = r2[(r2.failure_mode_id == r.failure_mode) & (r2.technique_id == r.technique)]
        selections[(r.failure_mode, r.technique)] = select_rationales(rows, r.estimate)

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

    if not args.no_slides:
        path = build_round2_slides(cells, selections, r2["personal_id"].nunique(),
                                   args.pptx or str(outdir / "round2_results.pptx"))
        if path:
            print(f"Wrote slides -> {path}  (1 overview + {len(cells)} case slides)")


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
    ap.add_argument("--pptx", default=None, help="slide output path (default: <out>/round{1,2}_results.pptx)")
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
