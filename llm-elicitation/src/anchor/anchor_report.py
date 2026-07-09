#!/usr/bin/env python3
"""
anchor_report.py — anchor pass-rate by configuration.

Runs the relative (pure-ordinal) anchors from anchors.yaml against several run
configurations and prints a PASS/FAIL/N-A matrix plus a per-config pass rate.
Intended for the "which configuration is trustworthy?" slides: it isolates the
effect of grounding (file-search) and of the discussion round.

NOTE on the runs: gpt-5.4-file-search/ and discussion_phase/ are byte-identical
(same Run ID 20260603_151329) — a single grounded run that includes the
discussion phase. We therefore represent it with its two Delphi rounds:
  file-search R1 = grounded, pre-discussion   (vs gpt-5.4 -> effect of grounding)
  file-search R2 = grounded, post-discussion  (vs R1      -> effect of discussion)

Usage:
  python3 anchor_report.py                       # default 3 configs, anchors.yaml
  python3 anchor_report.py --csv anchor_report.csv
  python3 anchor_report.py --config "label=path1,path2" --config "..."
"""
from __future__ import annotations
import argparse, csv, glob, os, re, sys
import anchor_check as ac

DEFAULT_CONFIGS = [
    ("gpt-5.4",        ["gpt-5.4/detailed_estimates.csv"]),
    ("file-search·R1", ["gpt-5.4-file-search/round_1_detailed_estimates.csv"]),
    ("file-search·R2", ["gpt-5.4-file-search/round_2_detailed_estimates.csv"]),
]

SYM = {"PASS": "PASS", "FAIL": "FAIL", "NA": " -- "}


def run(configs, anchors_path):
    """Return (anchors_meta, {config_label: {anchor_id: result}})."""
    per_config = {}
    meta = None
    for label, paths in configs:
        results = ac.check_anchors(paths, anchors_path)
        per_config[label] = {r["id"]: r for r in results}
        if meta is None:
            meta = [(r["id"], r.get("strength", "")) for r in results]
    return meta, per_config


def print_matrix(meta, per_config, labels):
    idw = max(len(i) for i, _ in meta) + 10  # room for id + strength tag
    colw = max(max(len(l) for l in labels), 6)

    header = " " * idw + "".join(f"{l:>{colw+2}}" for l in labels)
    print("\nAnchor pass-rate by configuration"
          "   (pure ordinal: PASS = ranking holds, magnitude ignored)\n")
    print(header)
    print("-" * len(header))

    for aid, strength in meta:
        tag = f"{aid} ({strength[:1]})" if strength else aid
        line = f"{tag:<{idw}}"
        for l in labels:
            line += f"{SYM[per_config[l][aid]['status']]:>{colw+2}}"
        print(line)

    print("-" * len(header))
    # summary rows
    def count(label, status):
        return sum(1 for r in per_config[label].values() if r["status"] == status)
    rate_line = f"{'pass rate (own denom.)':<{idw}}"
    for l in labels:
        p, f = count(l, "PASS"), count(l, "FAIL")
        denom = p + f
        rate = f"{p}/{denom}={100*p//denom if denom else 0}%"
        rate_line += f"{rate:>{colw+2}}"
    print(rate_line)

    # apples-to-apples: only anchors evaluable (non-NA) in EVERY config
    common = [aid for aid, _ in meta
              if all(per_config[l][aid]["status"] != "NA" for l in labels)]
    common_line = f"{f'pass rate (common {len(common)})':<{idw}}"
    for l in labels:
        p = sum(1 for aid in common if per_config[l][aid]["status"] == "PASS")
        common_line += f"{f'{p}/{len(common)}={100*p//len(common) if common else 0}%':>{colw+2}}"
    print(common_line)

    for status, name in [("PASS", "  passed"), ("FAIL", "  failed"), ("NA", "  n/a")]:
        line = f"{name:<{idw}}"
        for l in labels:
            line += f"{count(l, status):>{colw+2}}"
        print(line)


def print_movers(meta, per_config, labels):
    """Highlight anchors whose status changes across configs (the interesting ones)."""
    print("\nStatus changes across configs:")
    any_change = False
    for aid, _ in meta:
        statuses = [per_config[l][aid]["status"] for l in labels]
        if len(set(statuses)) > 1:
            any_change = True
            chain = " -> ".join(f"{l}:{s}" for l, s in zip(labels, statuses))
            print(f"  {aid}: {chain}")
    if not any_change:
        print("  (none — every anchor has the same verdict across all configs)")


def write_csv(path, meta, per_config, labels):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        cols = ["anchor_id", "strength", "description"]
        for l in labels:
            cols += [f"{l}__status", f"{l}__min_gap", f"{l}__expert_agreement"]
        w.writerow(cols)
        for aid, strength in meta:
            any_res = next(per_config[l][aid] for l in labels)
            row = [aid, strength, any_res.get("description", "")]
            for l in labels:
                r = per_config[l][aid]
                gap = "" if r.get("min_gap") is None else f"{r['min_gap']:.2f}"
                ea = "" if r.get("expert_agreement") is None else f"{r['expert_agreement']:.2f}"
                row += [r["status"], gap, ea]
            w.writerow(row)
    print(f"\nwrote {path}")


def parse_config_arg(spec):
    label, _, paths = spec.partition("=")
    return label, [p for p in paths.split(",") if p]


_TS_PREFIX = re.compile(r"^\d{8}_\d{6}-")  # strip "20260618_142022-" run-id prefix


def discover_runs(runs_dir):
    """Build one config per run sub-folder under `runs_dir`.

    A run folder is any immediate sub-directory containing *detailed_estimates.csv
    files. All such CSVs in the folder are passed together (round_1 + round_2 + …);
    anchor_check picks each cell's final round, so single- and multi-round runs are
    handled uniformly. The config label is the folder name with any leading
    run-id timestamp stripped.
    """
    configs = []
    for entry in sorted(os.listdir(runs_dir)):
        sub = os.path.join(runs_dir, entry)
        if not os.path.isdir(sub):
            continue
        csvs = sorted(glob.glob(os.path.join(sub, "*detailed_estimates.csv")))
        if not csvs:
            continue
        label = _TS_PREFIX.sub("", entry)
        configs.append((label, csvs))
    if not configs:
        raise SystemExit(f"No run folders with *detailed_estimates.csv found under {runs_dir}")
    return configs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anchors", default="anchors.yaml")
    ap.add_argument("--runs-dir",
                    help="auto-discover one config per run sub-folder under this dir")
    ap.add_argument("--config", action="append", default=[],
                    help='override configs: "label=path1,path2" (repeatable)')
    ap.add_argument("--csv", help="write the matrix to this CSV path")
    args = ap.parse_args(argv)

    if args.runs_dir:
        configs = discover_runs(args.runs_dir)
    elif args.config:
        configs = [parse_config_arg(c) for c in args.config]
    else:
        configs = DEFAULT_CONFIGS
    labels = [l for l, _ in configs]
    meta, per_config = run(configs, args.anchors)
    print_matrix(meta, per_config, labels)
    print_movers(meta, per_config, labels)
    if args.csv:
        write_csv(args.csv, meta, per_config, labels)
    return 0


if __name__ == "__main__":
    sys.exit(main())
