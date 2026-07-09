#!/usr/bin/env python3
"""
  For each expert we check whether the ordering the anchors expect actually holds.

PERT score = (minimum + 4 * estimate + maximum) / 6
  - a single "best guess" number that blends the expert's low / most-likely / high.
  - HIGHER pert = the technique is MORE effective (bigger % reduction vs SFT).

Two anchor types:
  technique_order : failure_mode is FIXED, we compare TECHNIQUES.
                    order = [best, ..., worst]  (best should have highest pert)
  failure_order   : technique is FIXED, we compare FAILURE MODES.
                    order = [best, ..., worst]

A check PASSES for an expert if every item in `order` has a strictly higher
pert than the item after it. If any item is missing from the data, the check
is N/A (null) for that expert.
"""

import argparse
import csv
import yaml
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 1. Load the estimates and compute a PERT score for every row
# ---------------------------------------------------------------------------
def load_pert_scores(csv_path):
    """
    Returns a nested dict:
        scores[expert][failure_mode][technique] = pert_score
    """
    scores = defaultdict(lambda: defaultdict(dict))

    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            expert = row["expert"].strip()
            technique = row["technique_ids"].strip()
            failure = row["failure_mode_id"].strip()

            # Some rows might have blank numbers; skip those safely.
            try:
                low = float(row["minimum"])
                mid = float(row["estimate"])
                high = float(row["maximum"])
            except (ValueError, KeyError):
                continue

            pert = (low + 4 * mid + high) / 6
            scores[expert][failure][technique] = pert

    return scores


# ---------------------------------------------------------------------------
# 2. Get the pert score for one (expert, failure_mode, technique) or None
# ---------------------------------------------------------------------------
def get_pert(scores, expert, failure_mode, technique):
    return scores.get(expert, {}).get(failure_mode, {}).get(technique)


# ---------------------------------------------------------------------------
# 3. Check a single anchor for a single expert
# ---------------------------------------------------------------------------
def check_anchor_for_expert(anchor, expert, scores):
    """
    Returns a dict describing the result:
        status : "PASS" | "FAIL" | "N/A"
        values : the pert score looked up for each item in the order
    """
    order = anchor["order"]  # list from MOST to LEAST effective

    # Look up the pert score for each item in the expected order.
    looked_up = []  # list of (item_name, pert_or_None)
    for item in order:
        if anchor["type"] == "technique_order":
            # failure mode is fixed; each item is a TECHNIQUE
            pert = get_pert(scores, expert, anchor["failure_mode"], item)
        else:  # failure_order
            # technique is fixed; each item is a FAILURE MODE
            pert = get_pert(scores, expert, item, anchor["technique"])
        looked_up.append((item, pert))

    # If ANY item is missing -> N/A (we can't fully judge the ordering)
    if any(pert is None for _, pert in looked_up):
        return {"status": "N/A", "values": looked_up}

    # Every item present: check that each is strictly greater than the next.
    values = [pert for _, pert in looked_up]
    passed = all(values[i] > values[i + 1] for i in range(len(values) - 1))

    return {"status": "PASS" if passed else "FAIL", "values": looked_up}



def _resolve_path(path: str, base_dir: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    cwd_candidate = (Path.cwd() / candidate).resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    script_candidate = (base_dir / candidate).resolve()
    if script_candidate.exists():
        return script_candidate

    return cwd_candidate

    
# ---------------------------------------------------------------------------
# 4. Run every anchor for every expert and print a report
# ---------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        nargs="+",
        required=True,
        help="one or more csv files from the same run"
    )
    parser.add_argument(
        "--anchors",
        default=str(Path(__file__).with_name("anchors.yaml")),
        help="yaml file containing the anchors to check"
    )
    parser.add_argument("--csv", help="optional CSV output path for per-expert anchor comparisons")
    parser.add_argument("--json", help="optional JSON output path")
    args = parser.parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    results_paths = [str(_resolve_path(path, script_dir)) for path in args.results]
    anchors_path = str(_resolve_path(args.anchors, script_dir))

    scores = load_pert_scores(results_paths[0]) 
    anchors = yaml.safe_load(open(anchors_path))["anchors"]
    experts = sorted(scores.keys())


    # Tally PASS / FAIL / N/A per expert while we go.
    tally = {expert: {"PASS": 0, "FAIL": 0, "N/A": 0} for expert in experts}
 
    for anchor in anchors:
        print("=" * 78)
        print(f"ANCHOR: {anchor['id']}")
        print(f"  {anchor['description']}")
 
        # Show what is being compared and in what order.
        if anchor["type"] == "technique_order":
            print(f"  type: technique_order | failure_mode = {anchor['failure_mode']}")
        else:
            print(f"  type: failure_order   | technique = {anchor['technique']}")
        print(f"  expected best -> worst: {anchor['order']}")
        print("-" * 78)
 
        for expert in experts:
            result = check_anchor_for_expert(anchor, expert, scores)
            tally[expert][result["status"]] += 1  # count it for the summary
 
            # Build a readable "item=score" string.
            parts = []
            for item, pert in result["values"]:
                parts.append(f"{item}={pert:.1f}" if pert is not None else f"{item}=NA")
            detail = "  >  ".join(parts)
 
            print(f"  [{result['status']:>4}] {expert:<45} {detail}")
        print()
 
    # -----------------------------------------------------------------------
    # 5. Overall pass percentage per expert
    #    pass % = PASS / (PASS + FAIL).  N/A anchors are ignored (not counted),
    #    because we couldn't judge them for lack of data.
    # -----------------------------------------------------------------------
    print("=" * 78)
    print("OVERALL PASS PERCENTAGE PER EXPERT")
    print("  (N/A anchors excluded from the percentage)")
 
    rows=[]
    for expert in experts:
        counts = tally[expert]
        evaluable = counts["PASS"] + counts["FAIL"]
        pass_pct = (counts["PASS"] / evaluable * 100) if evaluable else None
        rows.append({
            "expert": expert,
            "PASS": counts["PASS"],
            "FAIL": counts["FAIL"],
            "N/A": counts["N/A"],
            "pass_pct": pass_pct
        })
    
    sorted_rows = sorted(rows, key=lambda x: (x["pass_pct"] if x["pass_pct"] is not None else -1), reverse=True)

    print("-" * 98)
    print(f"  {'expert':<65}{'PASS':>6}{'FAIL':>6}{'N/A':>6}{'pass %':>9}")
    print("-" * 98)
    for row in sorted_rows:
        expert = row["expert"]
        counts = {"PASS": row["PASS"], "FAIL": row["FAIL"], "N/A": row["N/A"]}
        pass_pct = row["pass_pct"]
        print(f"  {expert:<65}{counts['PASS']:>6}{counts['FAIL']:>6}{counts['N/A']:>6}{(f'{pass_pct:.1f}%' if pass_pct is not None else 'N/A'):>9}")

 
if __name__ == "__main__":
    main()