#!/usr/bin/env python
"""Plot utilities for alignment elicitation run outputs.

Generates phase-level graphs from:
    output_data/runs/<run_id>/detailed_estimates.csv

Primary charts:
    - Technique effects with asymmetric uncertainty bars (min/max)
    - Expert disagreement by technique (std-dev and variance of estimates)

Additional analysis outputs:
    - Per-cell expert distribution boxplots (with outlier markers)
    - Uncertainty-width bars (max - min)
    - Mean-vs-disagreement scatter
    - Bootstrap rank-stability chart
    - CSV summaries with robust stats (median/IQR) and outlier flags
    - Simple observability-correction sensitivity table
"""

from __future__ import annotations

import argparse
import logging
from logging import config
import re
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)

RUN_ID_PATTERN = re.compile(r"^\d{8}_\d{6}$")


def _latest_run_dir(runs_root: Path) -> Optional[Path]:
    if not runs_root.is_dir():
        return None
    run_dirs = sorted(
        [
            p
            for p in runs_root.iterdir()
            if p.is_dir() and RUN_ID_PATTERN.match(p.name)
        ],
        key=lambda p: p.name,
    )
    return run_dirs[-1] if run_dirs else None


def _load_phase_data(csv_path: Path, phase: str, round_num: Optional[int] = None) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "phase" not in df.columns:
        raise ValueError("CSV does not contain a 'phase' column.")

    df = df[df["phase"] == phase].copy()
    if df.empty:
        return df

    for col in ["estimate", "minimum", "maximum", "confidence", "round_num"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if round_num is not None:
        # Keep estimates only from the requested Delphi round.
        df = df[df["round_num"] == round_num].dropna(subset=["estimate"])
        return df

    # Keep each expert's last-round estimate for each (technique stack, failure mode).
    key_cols = ["technique_ids", "failure_mode_id", "expert"]
    df = (
        df.sort_values("round_num")
        .dropna(subset=["estimate"])
        .groupby(key_cols, as_index=False)
        .tail(1)
    )
    return df


def _aggregate_for_plot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df["pert_score"] = (
        df["minimum"]
        + 4 * df["estimate"]
        + df["maximum"]
    ) / 6

    agg = (
        df.groupby(["failure_mode_name", "technique_names", "technique_ids"], as_index=False)
        .agg(
            minimum=("minimum", "mean"),
            maximum=("maximum", "mean"),
            pert_score=("pert_score", "mean"),
            n_experts=("expert", "nunique"),
        )
        .sort_values(["failure_mode_name", "pert_score"], ascending=[True, False])
    )

    return agg, df


def _aggregate_expert_variance(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df["pert_score"] = (
        df["minimum"]
        + 4 * df["estimate"]
        + df["maximum"]
    ) / 6

    agg = (
        df.groupby(["failure_mode_name", "technique_names", "technique_ids"], as_index=False)
        .agg(
            estimate_mean=("pert_score", "mean"),
            estimate_std=("pert_score", "std"),
            n_experts=("expert", "nunique"),
        )
        .sort_values(["failure_mode_name", "estimate_std"], ascending=[True, False])
    )

    # If only one expert contributed, std is NaN; treat as zero disagreement.
    agg["estimate_std"] = agg["estimate_std"].fillna(0.0)
    agg["estimate_variance"] = agg["estimate_std"] ** 2
    return agg


def _compute_tukey_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Returns expert-level Tukey outliers per (failure_mode, technique)."""
    if df.empty:
        return pd.DataFrame()

    rows = []
    group_cols = ["failure_mode_name", "technique_names", "technique_ids"]
    for keys, g in df.groupby(group_cols, as_index=False):
        failure_mode_name, technique_names, technique_ids = keys
        d = g[["expert", "pert_score"]].copy()
        d["pert_score"] = pd.to_numeric(d["pert_score"], errors="coerce")
        d = d.dropna(subset=["pert_score"])
        if d.empty:
            continue

        q1 = float(d["pert_score"].quantile(0.25))
        q3 = float(d["pert_score"].quantile(0.75))
        iqr = q3 - q1
        lo_fence = q1 - 1.5 * iqr
        hi_fence = q3 + 1.5 * iqr
        mask = (d["pert_score"] < lo_fence) | (d["pert_score"] > hi_fence)

        if not mask.any():
            continue

        for row in d.loc[mask].itertuples(index=False):
            rows.append(
                {
                    "failure_mode_name": failure_mode_name,
                    "technique_names": technique_names,
                    "technique_ids": technique_ids,
                    "expert": str(row.expert),
                    "pert_score": float(row.pert_score),
                    "tukey_lower_fence": lo_fence,
                    "tukey_upper_fence": hi_fence,
                }
            )

    return pd.DataFrame(rows)


def plot_phase_estimates(csv_path: Path, phase: str, output_png: Path, round_num: Optional[int] = None) -> Path:
    df = _load_phase_data(csv_path, phase, round_num=round_num)
    if df.empty:
        raise ValueError(f"No rows found for phase '{phase}' in {csv_path}.")

    agg, df = _aggregate_for_plot(df)
    outliers = _compute_tukey_outliers(df)
    print(f"the outliers are {outliers}")
    if agg.empty:
        raise ValueError("No valid numeric estimates found after aggregation.")

    failure_modes = list(agg["failure_mode_name"].unique())
    n = len(failure_modes)

    fig_h = max(4, 3.2 * n)
    fig, axes = plt.subplots(nrows=n, ncols=1, figsize=(12, fig_h), squeeze=False)

    for idx, fm in enumerate(failure_modes):
        ax = axes[idx][0]
        d = agg[agg["failure_mode_name"] == fm].copy()
        x = d["pert_score"].values
        y = list(range(len(d)))
        xerr_low = d["pert_score"] - d["minimum"]
        xerr_high = d["maximum"] - d["pert_score"]
        technique_to_y = {technique: y_pos for technique, y_pos in zip(d["technique_names"], y)}

        ax.errorbar(
            x,
            y,
            xerr=[xerr_low, xerr_high],
            fmt="o",
            color="#0b6e99",
            ecolor="#7aa6c2",
            elinewidth=2,
            capsize=4,
        )

        ax.set_yticks(list(y))
        ax.set_yticklabels(d["technique_names"])
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlabel("Estimated reduction vs SFT (%)")
        ax.set_title(f"{fm} (n experts per point: {int(d['n_experts'].max())})")

        # Annotate each point with exact values: estimate [minimum, maximum].
        for row, y_pos in zip(d.itertuples(index=False), y):
            label = f"{row.pert_score:.2f} [{row.minimum:.2f}, {row.maximum:.2f}]"
            ax.annotate(
                label,
                xy=(row.pert_score, y_pos),
                xytext=(8, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=8,
                color="#2f4f4f",
            )

        # Overlay expert-level Tukey outliers on top of the mean plot.
        if not outliers.empty:
            fm_outliers = outliers[outliers["failure_mode_name"] == fm].copy()
            if not fm_outliers.empty:
                outlier_label_added = False
                for technique_name, tdf in fm_outliers.groupby("technique_names"):
                    y_base = technique_to_y.get(technique_name)
                    if y_base is None:
                        continue

                    count = len(tdf)
                    if count == 1:
                        offsets = np.array([0.0])
                    else:
                        offsets = np.linspace(-0.15, 0.15, count)

                    x_vals = tdf["pert_score"].to_numpy(dtype=float)
                    y_vals = y_base + offsets
                    ax.scatter(
                        x_vals,
                        y_vals,
                        s=45,
                        marker="D",
                        color="#c0392b",
                        edgecolor="#7f1d13",
                        alpha=0.95,
                        label="Expert outlier (Tukey IQR)" if not outlier_label_added else None,
                        zorder=4,
                    )
                    outlier_label_added = True

                    outlier_experts = ", ".join(tdf["expert"].astype(str).tolist())
                    ax.annotate(
                        f"outliers={count}: {outlier_experts}",
                        xy=(99.2, y_base),
                        xytext=(0, 0),
                        textcoords="offset points",
                        ha="right",
                        va="center",
                        fontsize=7,
                        color="#7f1d13",
                    )

                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    ax.legend(handles, labels, loc="lower right", fontsize=8, frameon=False)

    title_phase = phase.replace("_", " ").title()
    if round_num is not None:
        title_phase = f"{title_phase} - Round {round_num}"
    fig.suptitle(f"{title_phase}: Technique Effect Estimates with Uncertainty", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)
    return output_png


def plot_expert_variance(csv_path: Path, phase: str, output_png: Path, round_num: Optional[int] = None) -> Path:
    df = _load_phase_data(csv_path, phase, round_num=round_num)
    if df.empty:
        raise ValueError(f"No rows found for phase '{phase}' in {csv_path}.")

    agg = _aggregate_expert_variance(df)
    if agg.empty:
        raise ValueError("No valid numeric estimates found for expert-variance plot.")

    failure_modes = list(agg["failure_mode_name"].unique())
    n = len(failure_modes)

    fig_h = max(4, 3.0 * n)
    fig, axes = plt.subplots(nrows=n, ncols=1, figsize=(12, fig_h), squeeze=False)

    for idx, fm in enumerate(failure_modes):
        ax = axes[idx][0]
        d = agg[agg["failure_mode_name"] == fm].copy()
        y = list(range(len(d)))

        bars = ax.barh(
            y,
            d["estimate_std"],
            color="#cc6f3c",
            alpha=0.85,
            edgecolor="#7f3f1a",
        )
        ax.set_yticks(list(y))
        ax.set_yticklabels(d["technique_names"])
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlabel("Expert disagreement (std-dev of estimate, percentage points)")
        ax.set_title(f"{fm} (n experts per bar: {int(d['n_experts'].max())})")

        for bar, row in zip(bars, d.itertuples(index=False)):
            label = f"std={row.estimate_std:.2f}, var={row.estimate_variance:.2f}"
            ax.annotate(
                label,
                xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                xytext=(8, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=8,
                color="#5a2d14",
            )

    title_phase = phase.replace("_", " ").title()
    if round_num is not None:
        title_phase = f"{title_phase} - Round {round_num}"
    fig.suptitle(f"{title_phase}: Expert Disagreement by Technique", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)
    return output_png


def plot_expert_boxplots(csv_path: Path, phase: str, output_png: Path) -> Path:
    df = _load_phase_data(csv_path, phase)
    if df.empty:
        raise ValueError(f"No rows found for phase '{phase}' in {csv_path}.")

    failure_modes = list(df["failure_mode_name"].unique())
    n = len(failure_modes)

    fig_h = max(4, 3.2 * n)
    fig, axes = plt.subplots(nrows=n, ncols=1, figsize=(12, fig_h), squeeze=False)

    for idx, fm in enumerate(failure_modes):
        ax = axes[idx][0]
        d = df[df["failure_mode_name"] == fm].copy()
        technique_order = (
            d.groupby("technique_names", as_index=False)["pert_score"]
            .mean()
            .sort_values("pert_score", ascending=False)["technique_names"]
            .tolist()
        )

        values = [d.loc[d["technique_names"] == t, "pert_score"].dropna().astype(float).to_numpy() for t in technique_order]
        positions = np.arange(len(technique_order))

        bp = ax.boxplot(
            values,
            vert=False,
            positions=positions,
            patch_artist=True,
            showfliers=True,
            widths=0.65,
            boxprops={"facecolor": "#bcd7e7", "edgecolor": "#3d6f8c"},
            whiskerprops={"color": "#3d6f8c"},
            capprops={"color": "#3d6f8c"},
            medianprops={"color": "#17425e", "linewidth": 2},
            flierprops={"marker": "o", "markerfacecolor": "#c0392b", "markeredgecolor": "#7f1d13", "markersize": 5, "alpha": 0.85},
        )
        _ = bp

        ax.set_yticks(positions)
        ax.set_yticklabels(technique_order)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlabel("Expert estimate (% reduction vs SFT)")
        ax.set_title(f"{fm} (distribution across experts)")

    title_phase = phase.replace("_", " ").title()
    fig.suptitle(f"{title_phase}: Expert Estimate Distributions (Boxplot + Outliers)", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)
    return output_png


def plot_uncertainty_width(csv_path: Path, phase: str, output_png: Path) -> Path:
    df = _load_phase_data(csv_path, phase)
    if df.empty:
        raise ValueError(f"No rows found for phase '{phase}' in {csv_path}.")

    agg = _aggregate_for_plot(df)
    if agg.empty:
        raise ValueError("No valid numeric estimates found for uncertainty-width plot.")

    agg["interval_width"] = (agg["maximum"] - agg["minimum"]).clip(lower=0)
    failure_modes = list(agg["failure_mode_name"].unique())
    n = len(failure_modes)

    fig_h = max(4, 3.0 * n)
    fig, axes = plt.subplots(nrows=n, ncols=1, figsize=(12, fig_h), squeeze=False)

    for idx, fm in enumerate(failure_modes):
        ax = axes[idx][0]
        d = agg[agg["failure_mode_name"] == fm].copy().sort_values("interval_width", ascending=False)
        y = list(range(len(d)))

        bars = ax.barh(y, d["interval_width"], color="#7b9e87", edgecolor="#47624d", alpha=0.9)
        ax.set_yticks(y)
        ax.set_yticklabels(d["technique_names"])
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlabel("Uncertainty width (max - min, percentage points)")
        ax.set_title(f"{fm} (wider = less certainty)")

        for bar, row in zip(bars, d.itertuples(index=False)):
            label = f"{row.interval_width:.2f}"
            ax.annotate(
                label,
                xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
                xytext=(8, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=8,
                color="#2f4635",
            )

    title_phase = phase.replace("_", " ").title()
    fig.suptitle(f"{title_phase}: Uncertainty Width by Technique", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)
    return output_png

from textwrap import fill


def plot_technique_failuremode_heatmap(
    csv_path,
    output_png,
    phase,
    round_num=None,
):
    df = _load_phase_data(csv_path, phase=phase, round_num=round_num)

    if df.empty:
        raise ValueError("No data found.")

    
    # PERT aggregation
    df["pert_score"] = (
        df["minimum"]
        + 4 * df["estimate"]
        + df["maximum"]
    ) / 6

    agg = (
        df.groupby(
            ["technique_names", "failure_mode_name"],
            as_index=False,
        )
        .agg(
            pert_score=("pert_score", "mean"),
            n_experts=("expert", "nunique"),
        )
    )
    
    # Heatmap matrix
    heatmap_df = agg.pivot(
        index="technique_names",
        columns="failure_mode_name",
        values="pert_score",
    )
    
    # Sort techniques by overall effectiveness
    technique_order = (
        heatmap_df.mean(axis=1)
        .sort_values(ascending=False)
        .index
    )

    heatmap_df = heatmap_df.loc[technique_order]

    # Add overall mean row (optional)
    # heatmap_df.loc["Overall Mean"] = heatmap_df.mean(axis=0)

    # Wrap long labels
    heatmap_df.index = [
        fill(str(x), width=22)
        for x in heatmap_df.index
    ]

    heatmap_df.columns = [
        fill(str(x), width=18)
        for x in heatmap_df.columns
    ]
    
    # Figure sizing
    plt.figure(
        figsize=(
            max(10, len(heatmap_df.columns) * 2.2),
            max(8, len(heatmap_df.index) * 1.0),
        )
    )
    
    # Heatmap
    ax = sns.heatmap(
        heatmap_df,
        annot=True,
        fmt=".1f",
        cmap=sns.color_palette(
            "blend:#f7fcf5,#00441b",
            as_cmap=True,
        ),
        vmin=0,
        vmax=70,  # stronger contrast
        linewidths=0.5,
        linecolor="white",
        cbar_kws={
            "label": "Estimated Reduction (%)"
        },
        annot_kws={
            "size": 10,
            "weight": "normal",
        },
    )

    # Annotation contrast
    for text in ax.texts:
        try:
            value = float(text.get_text())
            text.set_color(
                "white" if value >= 45 else "black"
            )
        except Exception:
            pass

    # Highlight highest-value cell
    max_row, max_col = divmod(
        heatmap_df.values.argmax(),
        heatmap_df.shape[1],
    )

    # Axis labels
    ax.set_xlabel(
        "Failure Mode",
        fontsize=11,
        labelpad=15,
    )

    ax.set_ylabel(
        "Alignment Technique",
        fontsize=11,
        labelpad=15,
    )
    
    # Tick formatting
    ax.tick_params(
        axis="x",
        rotation=0,
        pad=10,
        labelsize=9,
    )

    ax.tick_params(
        axis="y",
        rotation=0,
        pad=8,
        labelsize=9,
    )

        
    plt.title(
        f"\nTechnique Effectiveness by Failure Mode (Round {round_num})\n\n"
        f"Expert-Aggregated PERT Estimates (n={agg['n_experts'].max()} experts per cell)",
        fontsize=13,
        pad=20,
    )

    
    # Layout
    plt.tight_layout()
    plt.subplots_adjust(
        left=0.28,
        bottom=0.18,
        top=0.88,
    )
    
    output_png = Path(output_png)
    output_png.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    plt.savefig(
        output_png,
        dpi=300,
        bbox_inches="tight",
    )
    plt.close()

    return output_png


def generate_plots(
    run_id: Optional[str] = None,
    phase: str = "phase1_single_technique",
    total_round_num: Optional[int] = None,
    output: Optional[str] = None,
    runs_root: str = "output_data/runs",
) -> Path:
    """Generate a phase plot for a run and return the output PNG path.

    This function can be called from both python code and command-line.
    """
    runs_root_path = Path(runs_root)
    run_dir: Optional[Path]
    if run_id:
        run_dir = runs_root_path / run_id
    else:
        run_dir = _latest_run_dir(runs_root_path)

    if run_dir is None or not run_dir.is_dir():
        raise ValueError("Could not resolve run directory. Provide run_id or check runs_root.")

    print(f"total rounds: {total_round_num}")
    for round_num in range(1, total_round_num+1):
        print(f"Generating plots for round {round_num}...")
        csv_path = run_dir / f"round_{round_num}_detailed_estimates.csv"

        if output:
            output_png = Path(output)
            if round_num is not None:
                output_png = output_png.with_name(f"{output_png.stem}_round_{round_num}{output_png.suffix}")
            variance_png = output_png.with_name(f"{output_png.stem}_expert_variance{output_png.suffix}")
            heat_map_png = output_png.with_name(f"{output_png.stem}_heatmap{output_png.suffix}")
        else:
            phase_slug = f"round_{round_num}_{phase}" if round_num is not None else phase
            output_png = run_dir / "plots" / f"{phase_slug}_estimates.png"
            variance_png = run_dir / "plots" / f"{phase_slug}_expert_variance.png"
            heat_map_png = run_dir / "plots" / f"{phase_slug}_heatmap.png"

        result = plot_phase_estimates(
            csv_path=csv_path,
            phase=phase,
            output_png=output_png,
            round_num=round_num,
        )
        variance_result = plot_expert_variance(
            csv_path=csv_path,
            phase=phase,
            output_png=variance_png,
            round_num=round_num,
        )
        heat_map_result = plot_technique_failuremode_heatmap(
            csv_path=csv_path,
            output_png=heat_map_png,
            phase=phase,
            round_num=round_num,
        )

        logger.info(f"Saved plot (round {round_num}): {result}")
        logger.info(f"Saved plot (round {round_num}): {variance_result}")
        logger.info(f"Saved plot (round {round_num}): {heat_map_result}")


def generate_plots_cli() -> None:
    parser = argparse.ArgumentParser(description="Plot alignment elicitation results.")
    parser.add_argument("--run-id", help="Run ID under output_data/runs (default: latest).")
    parser.add_argument(
        "--phase",
        default="phase1_single_technique",
        help="Phase key from CSV (default: phase1_single_technique)",
    )
    parser.add_argument(
        "--round-num",
        type=int,
        help="Optional Delphi round number to plot explicitly (e.g., 2).",
    )
    parser.add_argument(
        "--output",
        help=(
            "Output PNG path for estimate chart "
            "(also writes '<stem>_expert_variance.png'). "
            "Default: output_data/runs/<run_id>/plots/<phase>_estimates.png"
        ),
    )
    parser.add_argument(
        "--runs-root",
        default="output_data/runs",
        help="Root directory containing run folders (default: output_data/runs)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    try:
        generate_plots(
            run_id=args.run_id,
            phase=args.phase,
            total_round_num=2 if args.round_num is None else args.round_num,
            output=args.output,
            runs_root=args.runs_root,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    generate_plots_cli()
