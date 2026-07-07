#!/usr/bin/env python3
"""
anchor_check.py — evaluate relative validation anchors against elicitation results.

An *anchor* is a ground-truth-ish relative claim we expect a trustworthy expert
panel to reproduce, e.g. "Constitutional Classifiers should outrank RLHF for
jailbreaking" or "RLHF should be less effective against sleeper-agent backdoors
than against jailbreaking". This script loads a results CSV (the per-expert
`detailed_estimates.csv` / `round_*_detailed_estimates.csv` format), aggregates
each technique x failure-mode cell across experts, and reports which anchors are
fulfilled (PASS / FAIL / N/A).

Two anchor types (both *relative* — no absolute target on the 0-100 scale):

  technique_order : within a fixed failure mode, a list of techniques that should
                    appear in descending effectiveness order (each beats the next).
  failure_order   : for a fixed technique, a list of failure modes that the
                    technique should be in descending effectiveness order on.

Each cell value = mean of per-expert `estimate` (% reduction vs SFT) at the cell's
final Delphi round. Besides the mean check, we also report *expert agreement*: the
fraction of experts who individually satisfy the ordering — a robustness signal for
whether the ranking is "clear" or just a thin average.

Usage:
  python3 anchor_check.py --results gpt-5.4/detailed_estimates.csv --anchors anchors.yaml
  python3 anchor_check.py --results discussion_phase/round_1_detailed_estimates.csv \
                          discussion_phase/round_2_detailed_estimates.csv \
                          --anchors anchors.yaml --json out.json
"""
from __future__ import annotations
import argparse, csv, json, sys
from collections import defaultdict

csv.field_size_limit(10_000_000)  # rationale fields are long


# ---------------------------------------------------------------------------
# Loading & aggregation
# ---------------------------------------------------------------------------
def load_rows(paths, phase="phase1_single_technique"):
    """Read one or more detailed_estimates CSVs into a flat list of dict rows.

    Keeps only error-free rows with a numeric estimate. If `phase` is given, keeps
    only that phase (the single-technique estimates); pass phase=None to keep all.
    """
    rows = []
    for p in paths:
        with open(p, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("error"):
                    continue
                if phase and r.get("phase") != phase:
                    continue
                # single-technique anchors only compare atomic techniques
                if "," in (r.get("technique_ids") or ""):
                    continue
                try:
                    r["_est"] = float(r["estimate"])
                    r["_round"] = int(r.get("round_num") or 0)
                except (TypeError, ValueError):
                    continue
                rows.append(r)
    return rows


def final_round_rows(rows):
    """For each (technique, failure_mode) cell keep only its highest-round rows.

    Handles Delphi early-stop, where different cells may finish on different rounds.
    """
    max_round = defaultdict(int)
    for r in rows:
        k = (r["technique_ids"], r["failure_mode_id"])
        max_round[k] = max(max_round[k], r["_round"])
    return [r for r in rows
            if r["_round"] == max_round[(r["technique_ids"], r["failure_mode_id"])]]


def available_failure_modes(rows):
    return sorted({r["failure_mode_id"] for r in rows})


def resolve_fms(value, available, aggregate_variants):
    """Map an anchor's failure-mode value to concrete ids present in the data.

    Exact id wins. With aggregate_variants=True, also pools sibling variants that
    share the base prefix (e.g. 'jailbreaking' -> jailbreaking + jailbreaking_generic).
    """
    if value in available and not aggregate_variants:
        return [value]
    if aggregate_variants:
        hits = [fm for fm in available if fm == value or fm.startswith(value + "_")]
        return hits
    return [value] if value in available else []


def cell(rows, technique_id, fm_ids):
    """Aggregate a cell across experts (and pooled fm variants).

    Returns (mean_estimate, per_expert_dict, n) or (None, {}, 0) if no data.
    per_expert maps expert -> mean estimate across the selected fm_ids.
    """
    by_expert = defaultdict(list)
    for r in rows:
        if r["technique_ids"] == technique_id and r["failure_mode_id"] in fm_ids:
            by_expert[r["expert"]].append(r["_est"])
    if not by_expert:
        return None, {}, 0
    per_expert = {e: sum(v) / len(v) for e, v in by_expert.items()}
    mean = sum(per_expert.values()) / len(per_expert)
    return mean, per_expert, len(per_expert)


# ---------------------------------------------------------------------------
# Anchor evaluation
# ---------------------------------------------------------------------------
def _ordered_agreement(per_expert_list):
    """Fraction of experts whose estimates are strictly descending across the
    ordered list of cells (only experts present in *all* listed cells count)."""
    common = set.intersection(*[set(pe) for pe in per_expert_list]) if per_expert_list else set()
    if not common:
        return None, 0
    ok = 0
    for e in common:
        seq = [pe[e] for pe in per_expert_list]
        if all(a > b for a, b in zip(seq, seq[1:])):
            ok += 1
    return ok / len(common), len(common)


def eval_anchor(anchor, rows, available):
    """Evaluate a single anchor. Returns a result dict with status PASS/FAIL/NA."""
    res = {"id": anchor.get("id"), "type": anchor.get("type"),
           "description": anchor.get("description", ""),
           "strength": anchor.get("strength", ""), "source": anchor.get("source", ""),
           "margin_required": float(anchor.get("margin", 0.0)),
           "status": "NA", "reason": "", "cells": []}
    agg_var = bool(anchor.get("aggregate_variants", False))
    margin = res["margin_required"]

    # Build the ordered list of cells to compare ------------------------------
    if anchor["type"] == "technique_order":
        fm_ids = resolve_fms(anchor["failure_mode"], available, agg_var)
        if not fm_ids:
            res["reason"] = f"failure_mode '{anchor['failure_mode']}' not present in results"
            return res
        res["scope"] = {"failure_mode": anchor["failure_mode"], "resolved": fm_ids}
        items = [(t, cell(rows, t, fm_ids)) for t in anchor["order"]]
        labels = anchor["order"]
    elif anchor["type"] == "failure_order":
        tech = anchor["technique"]
        resolved = [resolve_fms(fm, available, agg_var) for fm in anchor["order"]]
        items, labels = [], []
        for fm, ids in zip(anchor["order"], resolved):
            if not ids:
                res["reason"] = f"failure_mode '{fm}' not present in results"
                return res
            items.append((fm, cell(rows, tech, ids)))
            labels.append(fm)
        res["scope"] = {"technique": tech}
    else:
        res["reason"] = f"unknown anchor type '{anchor['type']}'"
        return res

    # Record cell values; bail to NA if any cell is missing -------------------
    missing = []
    per_expert_list, means = [], []
    for label, (mean, pe, n) in items:
        res["cells"].append({"label": label, "mean": mean, "n": n})
        if mean is None:
            missing.append(label)
        else:
            per_expert_list.append(pe)
            means.append(mean)
    if missing:
        res["reason"] = "no data for cell(s): " + ", ".join(missing)
        return res

    # Pure-ordinal check: every adjacent pair must strictly descend (A beats B).
    # `margin` (default 0) optionally also requires a minimum gap, but the default
    # workflow disregards magnitude entirely.
    gaps = [a - b for a, b in zip(means, means[1:])]
    res["min_gap"] = min(gaps)
    res["status"] = "PASS" if (res["min_gap"] > 0 and res["min_gap"] >= margin) else "FAIL"

    # Expert-agreement robustness signal --------------------------------------
    frac, ncommon = _ordered_agreement(per_expert_list)
    res["expert_agreement"] = frac
    res["expert_agreement_n"] = ncommon
    return res


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_report(results):
    tag = {"PASS": "PASS", "FAIL": "FAIL", "NA": "N/A "}
    n_pass = n_fail = n_na = 0
    for r in results:
        if r["status"] == "PASS": n_pass += 1
        elif r["status"] == "FAIL": n_fail += 1
        else: n_na += 1
        head = f"[{tag[r['status']]}] {r['id']}"
        if r.get("strength"):
            head += f"  ({r['strength']})"
        print(head)
        if r["description"]:
            print(f"       {r['description']}")
        if r["status"] == "NA":
            print(f"       -> N/A: {r['reason']}\n")
            continue
        for c in r["cells"]:
            mv = "  n/a" if c["mean"] is None else f"{c['mean']:6.1f}"
            print(f"         {c['label']:<32} = {mv}   (n={c['n']})")
        print(f"       min adjacent gap = {r['min_gap']:.1f}  "
              f"(required >= {r['margin_required']:.1f})  "
              f"{'OK' if r['status']=='PASS' else 'MISS'}")
        if r.get("expert_agreement") is not None:
            print(f"       expert agreement: {r['expert_agreement']*100:.0f}% "
                  f"({r['expert_agreement_n']} experts rated all cells)")
        print()
    print(f"== {n_pass} passed / {n_fail} failed / {n_na} n/a "
          f"of {len(results)} anchors ==")
    return n_fail


def load_anchors(path):
    if path.endswith((".yaml", ".yml")):
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    return data["anchors"] if isinstance(data, dict) else data


def check_anchors(results_paths, anchors_path, phase="phase1_single_technique"):
    """Importable entry point. Returns list of per-anchor result dicts."""
    rows = final_round_rows(load_rows(results_paths, phase=phase))
    available = available_failure_modes(rows)
    anchors = load_anchors(anchors_path)
    return [eval_anchor(a, rows, available) for a in anchors]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", nargs="+", required=True,
                    help="one or more detailed_estimates CSV files")
    ap.add_argument("--anchors", required=True, help="anchors YAML or JSON file")
    ap.add_argument("--phase", default="phase1_single_technique",
                    help="phase to keep ('all' to disable the filter)")
    ap.add_argument("--json", help="write machine-readable results to this path")
    args = ap.parse_args(argv)

    phase = None if args.phase == "all" else args.phase
    results = check_anchors(args.results, args.anchors, phase=phase)
    n_fail = print_report(results)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nwrote {args.json}")
    # exit non-zero only on hard failures, not on N/A
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
