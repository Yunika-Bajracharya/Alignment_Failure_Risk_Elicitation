
import csv
import numpy as np
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import logging

logger = logging.getLogger(__name__)


def plot_technique_ranking_summary(
    ranking_csv_path: Path,
    output_png: Path,
) -> Optional[Path]:
    """Plots mean reduction-vs-SFT ranking for each failure mode from ranking CSV."""
    if not ranking_csv_path.is_file():
        return None

    grouped: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    try:
        with open(ranking_csv_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if row.get("error"):
                    continue
                fm_name = str(row.get("failure_mode_name", "")).strip()
                t_name = str(row.get("technique_name", "")).strip()
                if not fm_name or not t_name:
                    continue
                try:
                    red = float(str(row.get("reduction_pct_vs_sft", "")).strip())
                    rank = int(float(str(row.get("rank", "")).strip()))
                except ValueError:
                    continue

                bucket = grouped[fm_name].setdefault(
                    t_name,
                    {"reductions": [], "ranks": []},
                )
                bucket["reductions"].append(red)
                bucket["ranks"].append(rank)
    except IOError as exc:
        logger.warning(f"Could not read ranking CSV for plot: {exc}")
        return None

    if not grouped:
        return None

    failure_modes = list(grouped.keys())
    fig_h = max(4, 3.2 * len(failure_modes))
    fig, axes = plt.subplots(nrows=len(failure_modes), ncols=1, figsize=(12, fig_h), squeeze=False)

    for idx, fm_name in enumerate(failure_modes):
        ax = axes[idx][0]
        rows = []
        for t_name, vals in grouped[fm_name].items():
            reductions = vals["reductions"]
            ranks = vals["ranks"]
            rows.append(
                {
                    "technique_name": t_name,
                    "mean_reduction": float(np.mean(reductions)) if reductions else 0.0,
                    "mean_rank": float(np.mean(ranks)) if ranks else 0.0,
                    "n": len(reductions),
                }
            )
        rows.sort(key=lambda r: r["mean_reduction"], reverse=True)

        y = list(range(len(rows)))
        bars = ax.barh(y, [r["mean_reduction"] for r in rows], color="#2a9d8f", alpha=0.9)
        ax.set_yticks(y)
        ax.set_yticklabels([r["technique_name"] for r in rows])
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlabel("Mean estimated reduction vs SFT (%)")
        ax.set_title(f"{fm_name} (aggregated expert ranking)")

        for bar, row in zip(bars, rows):
            label = f"{row['mean_reduction']:.2f}% | avg rank={row['mean_rank']:.2f} | n={row['n']}"
            ax.annotate(
                label,
                xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                xytext=(8, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=8,
                color="#1f3d39",
            )

    fig.suptitle("Technique Rankings by Failure Mode (vs SFT)", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)
    return output_png


def plot_ranking_comparison_summary(
    ranking_comparison_csv_path: Path,
    output_png: Path,
) -> Optional[Path]:
    """Plots mean absolute rank difference between all-at-once and one-by-one ranking."""
    if not ranking_comparison_csv_path.is_file():
        return None

    grouped: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    try:
        with open(ranking_comparison_csv_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if row.get("error"):
                    continue
                failure_mode_name = str(row.get("failure_mode_name", "")).strip()
                technique_name = str(row.get("technique_name", "")).strip()
                if not failure_mode_name or not technique_name:
                    continue
                try:
                    abs_rank_diff = float(str(row.get("abs_rank_diff", "")).strip())
                except ValueError:
                    continue
                grouped[failure_mode_name][technique_name].append(abs_rank_diff)
    except IOError as exc:
        logger.warning(f"Could not read ranking comparison CSV for plot: {exc}")
        return None

    if not grouped:
        return None

    failure_modes = list(grouped.keys())
    techniques = sorted(
        {technique for per_failure_mode in grouped.values() for technique in per_failure_mode.keys()}
    )

    matrix = np.full((len(techniques), len(failure_modes)), np.nan)
    for col_idx, failure_mode_name in enumerate(failure_modes):
        for row_idx, technique_name in enumerate(techniques):
            values = grouped[failure_mode_name].get(technique_name, [])
            if values:
                matrix[row_idx, col_idx] = float(np.mean(values))

    fig_w = max(7, 2.8 * len(failure_modes))
    fig_h = max(5, 0.55 * len(techniques) + 2.5)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    display_matrix = np.where(np.isnan(matrix), 0.0, matrix)
    im = ax.imshow(display_matrix, cmap="magma_r", aspect="auto", vmin=0)
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Mean absolute rank difference")

    ax.set_xticks(range(len(failure_modes)))
    ax.set_xticklabels(failure_modes, rotation=20, ha="right")
    ax.set_yticks(range(len(techniques)))
    ax.set_yticklabels(techniques)
    ax.set_title("All-at-once vs One-by-one Ranking Difference")

    for row_idx, technique_name in enumerate(techniques):
        for col_idx, failure_mode_name in enumerate(failure_modes):
            val = matrix[row_idx, col_idx]
            label = "-" if np.isnan(val) else f"{val:.2f}"
            ax.text(
                col_idx,
                row_idx,
                label,
                ha="center",
                va="center",
                color="white" if np.isnan(val) or val >= 1.5 else "black",
                fontsize=8,
            )

    fig.tight_layout()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)
    return output_png
