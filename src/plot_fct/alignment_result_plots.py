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
import re
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RUN_ID_PATTERN = re.compile(r"^\d{8}_\d{6}$")


OBSERVABILITY_RHO_SCENARIOS = {
    "optimistic_rho_0.8": 0.8,
    "neutral_rho_1.0": 1.0,
    "pessimistic_rho_1.2": 1.2,
}


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


def _load_phase_data(csv_path: Path, phase: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "phase" not in df.columns:
        raise ValueError("CSV does not contain a 'phase' column.")

    df = df[df["phase"] == phase].copy()
    if df.empty:
        return df

    for col in ["estimate", "minimum", "maximum", "confidence", "round_num"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

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

    agg = (
        df.groupby(["failure_mode_name", "technique_names", "technique_ids"], as_index=False)
        .agg(
            estimate=("estimate", "mean"),
            minimum=("minimum", "mean"),
            maximum=("maximum", "mean"),
            confidence=("confidence", "mean"),
            n_experts=("expert", "nunique"),
        )
        .sort_values(["failure_mode_name", "estimate"], ascending=[True, False])
    )

    agg["err_low"] = (agg["estimate"] - agg["minimum"]).clip(lower=0)
    agg["err_high"] = (agg["maximum"] - agg["estimate"]).clip(lower=0)
    return agg


def _aggregate_expert_variance(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    agg = (
        df.groupby(["failure_mode_name", "technique_names", "technique_ids"], as_index=False)
        .agg(
            estimate_mean=("estimate", "mean"),
            estimate_std=("estimate", "std"),
            n_experts=("expert", "nunique"),
        )
        .sort_values(["failure_mode_name", "estimate_std"], ascending=[True, False])
    )

    # If only one expert contributed, std is NaN; treat as zero disagreement.
    agg["estimate_std"] = agg["estimate_std"].fillna(0.0)
    agg["estimate_variance"] = agg["estimate_std"] ** 2
    return agg


def _compute_robust_stats(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    grouped = []
    for keys, g in df.groupby(["failure_mode_name", "technique_names", "technique_ids"], as_index=False):
        failure_mode_name, technique_names, technique_ids = keys
        vals = g["estimate"].dropna().astype(float)
        if vals.empty:
            continue

        q1 = float(vals.quantile(0.25))
        q3 = float(vals.quantile(0.75))
        iqr = q3 - q1
        lo_fence = q1 - 1.5 * iqr
        hi_fence = q3 + 1.5 * iqr
        outlier_mask = (vals < lo_fence) | (vals > hi_fence)

        grouped.append(
            {
                "failure_mode_name": failure_mode_name,
                "technique_names": technique_names,
                "technique_ids": technique_ids,
                "n_experts": int(g["expert"].nunique()),
                "estimate_mean": float(vals.mean()),
                "estimate_median": float(vals.median()),
                "estimate_std": float(vals.std(ddof=1)) if len(vals) > 1 else 0.0,
                "estimate_variance": float(vals.var(ddof=1)) if len(vals) > 1 else 0.0,
                "estimate_min": float(vals.min()),
                "estimate_max": float(vals.max()),
                "estimate_q1": q1,
                "estimate_q3": q3,
                "estimate_iqr": iqr,
                "tukey_lower_fence": lo_fence,
                "tukey_upper_fence": hi_fence,
                "outlier_count": int(outlier_mask.sum()),
                "outlier_experts": ", ".join(g.loc[outlier_mask, "expert"].astype(str).tolist()),
            }
        )

    out = pd.DataFrame(grouped)
    if out.empty:
        return out
    return out.sort_values(["failure_mode_name", "estimate_mean"], ascending=[True, False])


def _compute_observability_sensitivity(agg_effects: pd.DataFrame) -> pd.DataFrame:
    if agg_effects.empty:
        return agg_effects

    out = agg_effects[["failure_mode_name", "technique_names", "technique_ids", "estimate"]].copy()
    out.rename(columns={"estimate": "observed_reduction_pct"}, inplace=True)

    obs_frac = (out["observed_reduction_pct"] / 100.0).clip(lower=0.0, upper=1.0)
    for col, rho in OBSERVABILITY_RHO_SCENARIOS.items():
        corr = 1.0 - (1.0 - obs_frac) * rho
        out[f"{col}_corrected_reduction_pct"] = (corr.clip(lower=0.0, upper=1.0) * 100.0).round(3)

    return out.sort_values(["failure_mode_name", "observed_reduction_pct"], ascending=[True, False])


def _bootstrap_rank_stability(df: pd.DataFrame, n_bootstrap: int = 2000, random_seed: int = 42) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    rng = np.random.default_rng(seed=random_seed)
    rows = []

    for fm, fm_df in df.groupby("failure_mode_name"):
        techniques = list(fm_df["technique_names"].unique())
        if not techniques:
            continue

        samples_by_technique = {
            t: fm_df.loc[fm_df["technique_names"] == t, "estimate"].dropna().astype(float).to_numpy()
            for t in techniques
        }

        rank_counts = {t: {r: 0 for r in range(1, len(techniques) + 1)} for t in techniques}

        for _ in range(n_bootstrap):
            boot_means = {}
            for t, vals in samples_by_technique.items():
                if len(vals) == 0:
                    boot_means[t] = np.nan
                    continue
                draw = rng.choice(vals, size=len(vals), replace=True)
                boot_means[t] = float(np.mean(draw))

            ranked = [k for k, _ in sorted(boot_means.items(), key=lambda kv: (np.isnan(kv[1]), -kv[1] if not np.isnan(kv[1]) else np.inf))]
            for rank, t in enumerate(ranked, start=1):
                rank_counts[t][rank] += 1

        for t in techniques:
            for rank in range(1, len(techniques) + 1):
                rows.append(
                    {
                        "failure_mode_name": fm,
                        "technique_names": t,
                        "rank": rank,
                        "probability": rank_counts[t][rank] / float(n_bootstrap),
                    }
                )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out


def plot_phase_estimates(csv_path: Path, phase: str, output_png: Path) -> Path:
    df = _load_phase_data(csv_path, phase)
    if df.empty:
        raise ValueError(f"No rows found for phase '{phase}' in {csv_path}.")

    agg = _aggregate_for_plot(df)
    if agg.empty:
        raise ValueError("No valid numeric estimates found after aggregation.")

    failure_modes = list(agg["failure_mode_name"].unique())
    n = len(failure_modes)

    fig_h = max(4, 3.2 * n)
    fig, axes = plt.subplots(nrows=n, ncols=1, figsize=(12, fig_h), squeeze=False)

    for idx, fm in enumerate(failure_modes):
        ax = axes[idx][0]
        d = agg[agg["failure_mode_name"] == fm].copy()
        y = list(range(len(d)))

        ax.errorbar(
            d["estimate"],
            y,
            xerr=[d["err_low"], d["err_high"]],
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
            label = f"{row.estimate:.2f} [{row.minimum:.2f}, {row.maximum:.2f}]"
            ax.annotate(
                label,
                xy=(row.estimate, y_pos),
                xytext=(8, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=8,
                color="#2f4f4f",
            )

    title_phase = phase.replace("_", " ").title()
    fig.suptitle(f"{title_phase}: Technique Effect Estimates with Uncertainty", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)
    return output_png


def plot_expert_variance(csv_path: Path, phase: str, output_png: Path) -> Path:
    df = _load_phase_data(csv_path, phase)
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
            d.groupby("technique_names", as_index=False)["estimate"]
            .mean()
            .sort_values("estimate", ascending=False)["technique_names"]
            .tolist()
        )

        values = [d.loc[d["technique_names"] == t, "estimate"].dropna().astype(float).to_numpy() for t in technique_order]
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


def plot_mean_vs_disagreement(csv_path: Path, phase: str, output_png: Path) -> Path:
    df = _load_phase_data(csv_path, phase)
    if df.empty:
        raise ValueError(f"No rows found for phase '{phase}' in {csv_path}.")

    agg = _compute_robust_stats(df)
    if agg.empty:
        raise ValueError("No valid numeric estimates found for mean-vs-disagreement plot.")

    failure_modes = list(agg["failure_mode_name"].unique())
    n = len(failure_modes)

    fig_h = max(4, 3.1 * n)
    fig, axes = plt.subplots(nrows=n, ncols=1, figsize=(12, fig_h), squeeze=False)

    for idx, fm in enumerate(failure_modes):
        ax = axes[idx][0]
        d = agg[agg["failure_mode_name"] == fm].copy()

        ax.scatter(
            d["estimate_mean"],
            d["estimate_std"],
            s=80,
            c="#8c5e99",
            edgecolor="#5c2e68",
            alpha=0.85,
        )

        for row in d.itertuples(index=False):
            ax.annotate(
                row.technique_names,
                xy=(row.estimate_mean, row.estimate_std),
                xytext=(6, 6),
                textcoords="offset points",
                fontsize=8,
                color="#3f1f47",
            )

        ax.set_xlim(0, 100)
        ax.grid(alpha=0.25)
        ax.set_xlabel("Mean estimated reduction vs SFT (%)")
        ax.set_ylabel("Expert disagreement (std-dev)")
        ax.set_title(f"{fm} (lower y and higher x is better)")

    title_phase = phase.replace("_", " ").title()
    fig.suptitle(f"{title_phase}: Mean vs Disagreement", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)
    return output_png


def plot_rank_stability(csv_path: Path, phase: str, output_png: Path, n_bootstrap: int = 2000, random_seed: int = 42) -> Path:
    df = _load_phase_data(csv_path, phase)
    if df.empty:
        raise ValueError(f"No rows found for phase '{phase}' in {csv_path}.")

    rank_df = _bootstrap_rank_stability(df=df, n_bootstrap=n_bootstrap, random_seed=random_seed)
    if rank_df.empty:
        raise ValueError("No valid numeric estimates found for rank-stability plot.")

    failure_modes = list(rank_df["failure_mode_name"].unique())
    n = len(failure_modes)

    fig_h = max(4, 3.1 * n)
    fig, axes = plt.subplots(nrows=n, ncols=1, figsize=(12, fig_h), squeeze=False)

    rank_colors = ["#2e86ab", "#a23b72", "#f18f01", "#6b8e23", "#8c564b", "#5f9ea0"]

    for idx, fm in enumerate(failure_modes):
        ax = axes[idx][0]
        d = rank_df[rank_df["failure_mode_name"] == fm].copy()
        technique_order = (
            d[d["rank"] == 1].sort_values("probability", ascending=False)["technique_names"].tolist()
        )
        max_rank = int(d["rank"].max())
        y = np.arange(len(technique_order))
        left = np.zeros(len(technique_order))

        for r in range(1, max_rank + 1):
            vals = []
            for t in technique_order:
                sub = d[(d["technique_names"] == t) & (d["rank"] == r)]
                vals.append(float(sub["probability"].iloc[0]) if not sub.empty else 0.0)

            ax.barh(
                y,
                vals,
                left=left,
                color=rank_colors[(r - 1) % len(rank_colors)],
                edgecolor="white",
                alpha=0.9,
                label=f"Rank {r}",
            )
            left += np.array(vals)

        ax.set_yticks(y)
        ax.set_yticklabels(technique_order)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.0)
        ax.grid(axis="x", alpha=0.25)
        ax.set_xlabel("Bootstrap probability")
        ax.set_title(f"{fm} (rank stability over {n_bootstrap} bootstrap resamples)")

    handles, labels = axes[0][0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper center", ncol=min(len(labels), 5), frameon=False)

    title_phase = phase.replace("_", " ").title()
    fig.suptitle(f"{title_phase}: Rank Stability", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.94])

    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=180)
    plt.close(fig)
    return output_png


def generate_plots(
    run_id: Optional[str] = None,
    phase: str = "phase1_single_technique",
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

    csv_path = run_dir / "detailed_estimates.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(f"Missing CSV file: {csv_path}")

    if output:
        output_png = Path(output)
        variance_png = output_png.with_name(f"{output_png.stem}_expert_variance{output_png.suffix}")
        boxplot_png = output_png.with_name(f"{output_png.stem}_expert_boxplots{output_png.suffix}")
        uncertainty_png = output_png.with_name(f"{output_png.stem}_uncertainty_width{output_png.suffix}")
        scatter_png = output_png.with_name(f"{output_png.stem}_mean_vs_disagreement{output_png.suffix}")
        rank_png = output_png.with_name(f"{output_png.stem}_rank_stability{output_png.suffix}")
        robust_stats_csv = output_png.with_name(f"{output_png.stem}_robust_stats.csv")
        observability_csv = output_png.with_name(f"{output_png.stem}_observability_sensitivity.csv")
    else:
        output_png = run_dir / "plots" / f"{phase}_estimates.png"
        variance_png = run_dir / "plots" / f"{phase}_expert_variance.png"
        boxplot_png = run_dir / "plots" / f"{phase}_expert_boxplots.png"
        uncertainty_png = run_dir / "plots" / f"{phase}_uncertainty_width.png"
        scatter_png = run_dir / "plots" / f"{phase}_mean_vs_disagreement.png"
        rank_png = run_dir / "plots" / f"{phase}_rank_stability.png"
        robust_stats_csv = run_dir / "plots" / f"{phase}_robust_stats.csv"
        observability_csv = run_dir / "plots" / f"{phase}_observability_sensitivity.csv"

    result = plot_phase_estimates(csv_path=csv_path, phase=phase, output_png=output_png)
    variance_result = plot_expert_variance(csv_path=csv_path, phase=phase, output_png=variance_png)
    boxplot_result = plot_expert_boxplots(csv_path=csv_path, phase=phase, output_png=boxplot_png)
    uncertainty_result = plot_uncertainty_width(csv_path=csv_path, phase=phase, output_png=uncertainty_png)
    scatter_result = plot_mean_vs_disagreement(csv_path=csv_path, phase=phase, output_png=scatter_png)
    rank_result = plot_rank_stability(csv_path=csv_path, phase=phase, output_png=rank_png)

    raw_df = _load_phase_data(csv_path=csv_path, phase=phase)
    robust_df = _compute_robust_stats(raw_df)
    agg_df = _aggregate_for_plot(raw_df)
    observability_df = _compute_observability_sensitivity(agg_df)

    robust_stats_csv.parent.mkdir(parents=True, exist_ok=True)
    robust_df.to_csv(robust_stats_csv, index=False)
    observability_df.to_csv(observability_csv, index=False)

    logger.info(f"Saved plot: {result}")
    logger.info(f"Saved plot: {variance_result}")
    logger.info(f"Saved plot: {boxplot_result}")
    logger.info(f"Saved plot: {uncertainty_result}")
    logger.info(f"Saved plot: {scatter_result}")
    logger.info(f"Saved plot: {rank_result}")
    logger.info(f"Saved analysis table: {robust_stats_csv}")
    logger.info(f"Saved analysis table: {observability_csv}")
    return result


def generate_plots_cli() -> None:
    parser = argparse.ArgumentParser(description="Plot alignment elicitation results.")
    parser.add_argument("--run-id", help="Run ID under output_data/runs (default: latest).")
    parser.add_argument(
        "--phase",
        default="phase1_single_technique",
        help="Phase key from CSV (default: phase1_single_technique)",
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
            output=args.output,
            runs_root=args.runs_root,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    generate_plots_cli()
