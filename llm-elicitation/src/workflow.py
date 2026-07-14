# src/workflow.py
"""
Delphi elicitation workflow for AI alignment failure-risk quantification.

Phase 1  — Single-technique × failure-mode estimation
  For every (alignment_technique, failure_mode) pair the panel of simulated
  experts iterates through Delphi rounds, starting from the
  ``initial_failure_estimation`` prompt and refining with the
  ``subsequent_failure_estimation`` prompt.

Phase 2  — Defense-in-depth (stacked technique) estimation
  For each technique combination (pairs and optionally a preset triple) and
  for every failure mode the panel estimates the *residual* frequency when
  both (or all) techniques are applied simultaneously, anchored on the
  Phase-1 single-technique medians.

Results are written progressively:
  - JSON snapshot : <output_dir>/runs/<run_id>/full_results.json
  - CSV           : <output_dir>/runs/<run_id>/detailed_estimates.csv
  - Run registry  : <output_dir>/run_registry.json
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import time
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None  # type: ignore
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore

from config import AppConfig
from data_models import (
    AlignmentInputData,
    AlignmentTechnique,
    DeploymentScenario,
    FailureMode,
    ExpertsByDomain,
    ExpertProfile
)
from llm_api import (
    reset_token_counts,
    get_token_counts
)

from plot_fct.alignment_result_plots import generate_plots
from plot_fct.ranking_plots import plot_technique_ranking_summary, plot_ranking_comparison_summary
from run_io import (
    init_alignment_run,
    append_rows_to_csv,
    append_ranking_rows_to_csv,
    append_ranking_comparison_rows_to_csv,
    save_json,
    update_registry,
)
from expert_selection import (
    precompute_technique_contexts_for_experts,
    precompute_failure_mode_contexts_for_experts,
    experts_for_failure_mode
)
from prompt_builders import scenario_for_failure_mode
from idea_engine import (
    run_idea_cell,
    expert_phase1_round,
    expert_phase2_round,
    aggregate_final,
    expert_technique_ranking,
)

logger = logging.getLogger(__name__)


ClientType = Union["AsyncAnthropic", "AsyncOpenAI"]
SemaphoreType = asyncio.Semaphore


def _collect_phase1_final_estimates(
    overall_results: Dict[str, Any],
) -> Dict[Tuple[str, str, str], float]:
    """Returns ``(failure_mode_id, expert_name, technique_id) -> final estimate``."""
    estimates: Dict[Tuple[str, str, str], float] = {}

    for technique_entry in overall_results.get("phase1_results", []):
        technique_id = str(technique_entry.get("technique_id", "")).strip()
        if not technique_id:
            continue

        for failure_mode_result in technique_entry.get("failure_mode_results", []):
            failure_mode_id = str(failure_mode_result.get("failure_mode_id", "")).strip()
            rounds_data = failure_mode_result.get("rounds_data") or []
            if not failure_mode_id or not rounds_data:
                continue

            final_round = rounds_data[-1]
            for response in final_round.get("responses", []):
                if response.get("error") or response.get("estimate") is None:
                    continue
                expert_name = str(response.get("expert", "")).strip()
                if not expert_name:
                    continue
                try:
                    estimates[(failure_mode_id, expert_name, technique_id)] = float(response["estimate"])
                except (TypeError, ValueError):
                    continue

    return estimates


def _compare_ranking_modes(
    run_info: Dict[str, Any],
    overall_results: Dict[str, Any],
    techniques: List[AlignmentTechnique],
) -> List[Dict[str, Any]]:
    """Compares all-at-once rankings against one-by-one implied rankings per expert."""
    phase1_estimates = _collect_phase1_final_estimates(overall_results)
    technique_name_by_id = {t.id: t.name for t in techniques}
    comparison_results: List[Dict[str, Any]] = []

    for ranking_block in overall_results.get("technique_ranking_results", []):
        failure_mode_id = str(ranking_block.get("failure_mode_id", "")).strip()
        failure_mode_name = str(ranking_block.get("failure_mode_name", "")).strip()
        scenario_name = str(ranking_block.get("deployment_scenario_name", "")).strip()
        expert_comparisons: List[Dict[str, Any]] = []

        for expert_result in ranking_block.get("expert_rankings", []):
            expert_name = str(expert_result.get("expert", "")).strip()
            if not expert_name:
                continue

            all_at_once_rows = expert_result.get("rankings") or []
            if expert_result.get("error") or not all_at_once_rows:
                append_ranking_comparison_rows_to_csv(
                    run_info["ranking_comparison_csv_path"],
                    [
                        {
                            "run_id": run_info["run_id"],
                            "failure_mode_id": failure_mode_id,
                            "failure_mode_name": failure_mode_name,
                            "deployment_scenario_name": scenario_name,
                            "expert": expert_name,
                            "technique_id": "",
                            "technique_name": "",
                            "one_by_one_estimate": "",
                            "one_by_one_rank": "",
                            "all_at_once_reduction_pct_vs_sft": "",
                            "all_at_once_rank": "",
                            "rank_diff": "",
                            "abs_rank_diff": "",
                            "error": str(expert_result.get("error", "Missing all-at-once ranking")),
                        }
                    ],
                )
                expert_comparisons.append(
                    {
                        "expert": expert_name,
                        "mean_abs_rank_diff": None,
                        "matched_techniques": 0,
                        "error": str(expert_result.get("error", "Missing all-at-once ranking")),
                    }
                )
                continue

            single_rows: List[Dict[str, Any]] = []
            missing_techniques: List[str] = []
            for technique in techniques:
                estimate = phase1_estimates.get((failure_mode_id, expert_name, technique.id))
                if estimate is None:
                    missing_techniques.append(technique.id)
                    continue
                single_rows.append(
                    {
                        "technique_id": technique.id,
                        "technique_name": technique.name,
                        "estimate": estimate,
                    }
                )

            if missing_techniques:
                error_text = (
                    "Missing one-by-one estimates for techniques: "
                    + ", ".join(missing_techniques)
                )
                append_ranking_comparison_rows_to_csv(
                    run_info["ranking_comparison_csv_path"],
                    [
                        {
                            "run_id": run_info["run_id"],
                            "failure_mode_id": failure_mode_id,
                            "failure_mode_name": failure_mode_name,
                            "deployment_scenario_name": scenario_name,
                            "expert": expert_name,
                            "technique_id": "",
                            "technique_name": "",
                            "one_by_one_estimate": "",
                            "one_by_one_rank": "",
                            "all_at_once_reduction_pct_vs_sft": "",
                            "all_at_once_rank": "",
                            "rank_diff": "",
                            "abs_rank_diff": "",
                            "error": error_text,
                        }
                    ],
                )
                expert_comparisons.append(
                    {
                        "expert": expert_name,
                        "mean_abs_rank_diff": None,
                        "matched_techniques": 0,
                        "error": error_text,
                    }
                )
                continue

            single_rows.sort(key=lambda row: (row["estimate"], row["technique_id"]))
            single_rank_by_id = {
                row["technique_id"]: {
                    "rank": idx,
                    "estimate": row["estimate"],
                }
                for idx, row in enumerate(single_rows, start=1)
            }

            csv_rows: List[Dict[str, Any]] = []
            abs_diffs: List[int] = []
            comparison_rows: List[Dict[str, Any]] = []
            for all_at_once in all_at_once_rows:
                technique_id = str(all_at_once.get("technique_id", "")).strip()
                if technique_id not in single_rank_by_id:
                    continue

                try:
                    all_at_once_rank = int(all_at_once.get("rank"))
                except (TypeError, ValueError):
                    continue

                single_rank = int(single_rank_by_id[technique_id]["rank"])
                one_by_one_estimate = float(single_rank_by_id[technique_id]["estimate"])
                rank_diff = all_at_once_rank - single_rank
                abs_rank_diff = abs(rank_diff)
                abs_diffs.append(abs_rank_diff)

                comparison_row = {
                    "technique_id": technique_id,
                    "technique_name": technique_name_by_id.get(technique_id, technique_id),
                    "one_by_one_estimate": one_by_one_estimate,
                    "one_by_one_rank": single_rank,
                    "all_at_once_reduction_pct_vs_sft": all_at_once.get("reduction_pct"),
                    "all_at_once_rank": all_at_once_rank,
                    "rank_diff": rank_diff,
                    "abs_rank_diff": abs_rank_diff,
                }
                comparison_rows.append(comparison_row)
                csv_rows.append(
                    {
                        "run_id": run_info["run_id"],
                        "failure_mode_id": failure_mode_id,
                        "failure_mode_name": failure_mode_name,
                        "deployment_scenario_name": scenario_name,
                        "expert": expert_name,
                        **comparison_row,
                        "error": "",
                    }
                )

            append_ranking_comparison_rows_to_csv(
                run_info["ranking_comparison_csv_path"],
                csv_rows,
            )
            expert_comparisons.append(
                {
                    "expert": expert_name,
                    "mean_abs_rank_diff": float(np.mean(abs_diffs)) if abs_diffs else None,
                    "matched_techniques": len(comparison_rows),
                    "rows": comparison_rows,
                    "error": None,
                }
            )

        comparison_results.append(
            {
                "failure_mode_id": failure_mode_id,
                "failure_mode_name": failure_mode_name,
                "deployment_scenario_name": scenario_name,
                "expert_comparisons": expert_comparisons,
            }
        )

    return comparison_results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase runners
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _run_phase1(
    experts: List[ExpertProfile],
    techniques: List[AlignmentTechnique],
    failure_modes: List[FailureMode],
    client: Any,
    semaphore: SemaphoreType,
    config: AppConfig,
    prompts: Dict[str, str],
    run_info: Dict[str, Any],
    overall_results: Dict[str, Any],
    experts_by_domain: Optional[ExpertsByDomain] = None,  # NEW: domain-grouped experts
) -> Dict[Tuple[str, str], Optional[float]]:
    """
    Phase 1: Delphi estimation for every (technique × failure_mode) pair.
    
    For each failure mode, selects the appropriate expert panel (shared AI safety
    experts + domain-specific experts) using the failure_mode_domain_mapping.

    Returns a mapping ``(technique_id, failure_mode_id) → final_median_estimate``
    used as input to Phase 2.
    """
    aln = config.workflow_settings
    total_cells = len(techniques) * len(failure_modes)
    done = 0

    single_tech_medians: Dict[Tuple[str, str], Optional[float]] = {}

    logger.info(
        f"\n{'='*60}\n"
        f"PHASE 1 — Single-technique × failure-mode Delphi\n"
        f"  Techniques : {len(techniques)}\n"
        f"  Failure modes: {len(failure_modes)}\n"
        f"  Total cells  : {total_cells}\n"
        f"{'='*60}"
    )
    
    # Collect all unique experts from all failure modes
    all_unique_experts: Dict[str, ExpertProfile] = {}
    for failure_mode in failure_modes:
        failure_mode_experts = experts_for_failure_mode(
            failure_mode, experts_by_domain, experts, config
        )
        for expert in failure_mode_experts:
            if expert.name not in all_unique_experts:
                all_unique_experts[expert.name] = expert
    
    all_experts_list = list(all_unique_experts.values())
    logger.info(f"Unique experts across all failure modes: {len(all_experts_list)}")
    
    # Pre-compute technique contexts for all (technique, expert) pairs
    technique_context_cache = await precompute_technique_contexts_for_experts(
        techniques=techniques,
        all_experts=all_experts_list,
        client=client,
        config=config,
        project_root=Path.cwd(),
        semaphore=semaphore,
        output_dir=run_info["run_dir"],
    )

    # Pre-compute failure-mode contexts for all (failure_mode, expert) pairs
    failure_mode_context_cache = await precompute_failure_mode_contexts_for_experts(
        failure_modes=failure_modes,
        all_experts=all_experts_list,
        client=client,
        config=config,
        project_root=Path.cwd(),
        semaphore=semaphore,
        output_dir=run_info["run_dir"],
    )

    for technique in techniques:
        tech_result_entry: Dict[str, Any] = {
            "technique_id": technique.id,
            "technique_name": technique.name,
            "failure_mode_results": [],
        }
        # Pre-append so inner loop can snapshot JSON incrementally
        overall_results["phase1_results"].append(tech_result_entry)

        for failure_mode in failure_modes:
            done += 1
            cell_label = f"P1 | {technique.id} × {failure_mode.id} [{done}/{total_cells}]"
            logger.info(f"\n{'─'*60}\n{cell_label}\n{'─'*60}")
            scenario = scenario_for_failure_mode(failure_mode)
            
            # Select the expert panel for this failure mode
            failure_mode_experts = experts_for_failure_mode(
                failure_mode, experts_by_domain, experts, config
            )

            def _make_expert_coro(
                exp: ExpertProfile,
                rnd: int,
                prev: Optional[List],
                _tech=technique,
                _fm=failure_mode,
            ):
                return expert_phase1_round(
                    expert=exp,
                    technique=_tech,
                    failure_mode=_fm,
                    scenario=scenario,
                    round_num=rnd,
                    prev_round_responses=prev,
                    client=client,
                    semaphore=semaphore,
                    config=config,
                    prompts=prompts,
                    technique_file_context=None,
                    technique_context_cache=technique_context_cache,
                    failure_mode_file_context=None,
                    failure_mode_context_cache=failure_mode_context_cache,
                )

            rounds_data, converged_at = await run_idea_cell(
                experts=failure_mode_experts,  # Use selected panel instead of global experts
                expert_coroutine_factory=_make_expert_coro,
                idea_rounds=aln.idea_rounds,
                convergence_threshold=aln.convergence_threshold,
                cell_label=cell_label,
            )

            agg = aggregate_final(rounds_data)
            single_tech_medians[(technique.id, failure_mode.id)] = agg["estimate"]

            fm_result: Dict[str, Any] = {
                "failure_mode_id": failure_mode.id,
                "failure_mode_name": failure_mode.name,
                "deployment_scenario_name": scenario.name,
                "rounds_data": rounds_data,
                "converged_at_round": converged_at,
                **agg,
            }
            # tech_result_entry is the same dict object already in overall_results
            tech_result_entry["failure_mode_results"].append(fm_result)

            # Persist round-by-round to CSV
            for rd in rounds_data:
                append_rows_to_csv(
                    csv_path=run_info[f"round_{rd['round']}_csv_path"],
                    phase="phase1_single_technique",
                    technique_ids=[technique.id],
                    technique_names=[technique.name],
                    failure_mode=failure_mode,
                    round_num=rd["round"],
                    responses=rd["responses"],
                    run_id=run_info["run_id"],
                )
                

            # Snapshot JSON after each cell
            save_json(run_info["json_path"], overall_results)

            est_str = f"{agg['estimate']:.3f}" if agg["estimate"] is not None else "N/A"
            logger.info(
                f"  {cell_label} → final estimate = {est_str} incidents/year"
            )

        # Technique complete – final snapshot already written in inner loop
        save_json(run_info["json_path"], overall_results)

    return single_tech_medians


async def _run_phase1_technique_ranking(
    experts: List[ExpertProfile],
    techniques: List[AlignmentTechnique],
    failure_modes: List[FailureMode],
    single_tech_medians: Dict[Tuple[str, str], Optional[float]],
    client: Any,
    semaphore: SemaphoreType,
    config: AppConfig,
    prompts: Dict[str, str],
    run_info: Dict[str, Any],
    overall_results: Dict[str, Any],
    experts_by_domain: Optional[ExpertsByDomain] = None,
) -> None:
    """Runs an additional ranking pass: experts rank all techniques per failure mode."""
    total_cells = len(failure_modes)
    done = 0
    technique_name_by_id = {t.id: t.name for t in techniques}

    logger.info(
        f"\n{'='*60}\n"
        f"PHASE 1B — Cross-technique ranking vs SFT\n"
        f"  Failure modes: {len(failure_modes)}\n"
        f"  Techniques   : {len(techniques)}\n"
        f"  Total cells  : {total_cells}\n"
        f"{'='*60}"
    )

    for failure_mode in failure_modes:
        done += 1
        cell_label = f"P1B | ranking all techniques for {failure_mode.id} [{done}/{total_cells}]"
        logger.info(f"\n{'─'*60}\n{cell_label}\n{'─'*60}")

        scenario = scenario_for_failure_mode(failure_mode)
        failure_mode_experts = experts_for_failure_mode(
            failure_mode, experts_by_domain, experts, config
        )

        context_lines: List[str] = []
        for t in techniques:
            est = single_tech_medians.get((t.id, failure_mode.id))
            est_str = f"{est:.2f}%" if est is not None else "N/A"
            context_lines.append(f"- {t.name} (id={t.id}): {est_str} reduction vs SFT")
        per_tech_context = "\n".join(context_lines)

        tasks = [
            expert_technique_ranking(
                expert=exp,
                techniques=techniques,
                failure_mode=failure_mode,
                scenario=scenario,
                per_technique_estimate_context=per_tech_context,
                client=client,
                semaphore=semaphore,
                config=config,
                prompts=prompts,
            )
            for exp in failure_mode_experts
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        expert_rankings: List[Dict[str, Any]] = []
        for idx, res in enumerate(raw_results):
            exp_name = failure_mode_experts[idx].name
            if isinstance(res, Exception):
                expert_rankings.append(
                    {
                        "expert": exp_name,
                        "rankings": [],
                        "rationale": "",
                        "error": str(res),
                    }
                )
            else:
                expert_rankings.append(res)

        reductions_by_tech: Dict[str, List[float]] = defaultdict(list)
        ranks_by_tech: Dict[str, List[int]] = defaultdict(list)
        for e in expert_rankings:
            if e.get("error"):
                continue
            for row in e.get("rankings", []):
                tid = str(row.get("technique_id", ""))
                red = row.get("reduction_pct")
                rnk = row.get("rank")
                if tid and isinstance(red, (int, float)) and isinstance(rnk, int):
                    reductions_by_tech[tid].append(float(red))
                    ranks_by_tech[tid].append(int(rnk))

        aggregate_ranking: List[Dict[str, Any]] = []
        for t in techniques:
            reds = reductions_by_tech.get(t.id, [])
            rnks = ranks_by_tech.get(t.id, [])
            aggregate_ranking.append(
                {
                    "technique_id": t.id,
                    "technique_name": t.name,
                    "mean_reduction_pct_vs_sft": float(np.mean(reds)) if reds else None,
                    "median_reduction_pct_vs_sft": float(np.median(reds)) if reds else None,
                    "mean_rank": float(np.mean(rnks)) if rnks else None,
                    "n_experts": len(reds),
                }
            )

        aggregate_ranking.sort(
            key=lambda r: r["mean_reduction_pct_vs_sft"]
            if r["mean_reduction_pct_vs_sft"] is not None
            else -1e9,
            reverse=True,
        )

        for expert_result in expert_rankings:
            append_ranking_rows_to_csv(
                ranking_csv_path=run_info["ranking_csv_path"],
                run_id=run_info["run_id"],
                failure_mode=failure_mode,
                scenario=scenario,
                expert_result=expert_result,
                technique_name_by_id=technique_name_by_id,
            )

        overall_results["technique_ranking_results"].append(
            {
                "failure_mode_id": failure_mode.id,
                "failure_mode_name": failure_mode.name,
                "deployment_scenario_name": scenario.name,
                "expert_rankings": expert_rankings,
                "aggregate_ranking": aggregate_ranking,
            }
        )
        save_json(run_info["json_path"], overall_results)

        if aggregate_ranking and aggregate_ranking[0].get("technique_name"):
            logger.info(
                "  ✓ %s → top ranked technique: %s",
                cell_label,
                aggregate_ranking[0]["technique_name"],
            )


async def _run_phase2(
    experts: List[ExpertProfile],
    techniques: List[AlignmentTechnique],
    failure_modes: List[FailureMode],
    single_tech_medians: Dict[Tuple[str, str], Optional[float]],
    client: Any,
    semaphore: SemaphoreType,
    config: AppConfig,
    prompts: Dict[str, str],
    run_info: Dict[str, Any],
    overall_results: Dict[str, Any],
    experts_by_domain: Optional[ExpertsByDomain] = None,  # NEW: domain-grouped experts
) -> None:
    """
    Phase 2: Defense-in-depth Delphi for technique combinations.
    
    For each failure mode, selects the appropriate expert panel (shared AI safety
    experts + domain-specific experts) using the failure_mode_domain_mapping.
    """
    aln = config.workflow_settings

    # Build the list of technique stacks to evaluate
    stacks: List[List[AlignmentTechnique]] = []
    # All C(n,2) pairs
    for t1, t2 in combinations(techniques, 2):
        stacks.append([t1, t2])
    # Optionally add a preset triple
    if (
        aln.technique_combinations == "pairwise_plus_triple"
        and aln.preset_triple
    ):
        triple_techniques = [
            t for t in techniques if t.id in aln.preset_triple
        ]
        if len(triple_techniques) >= 2:
            stacks.append(triple_techniques[:3])
        else:
            logger.warning(
                "Preset triple includes technique IDs not in the active technique list; "
                "skipping triple."
            )

    total_cells = len(stacks) * len(failure_modes)
    done = 0

    logger.info(
        f"\n{'='*60}\n"
        f"PHASE 2 — Defense-in-depth combinations\n"
        f"  Stacks       : {len(stacks)}\n"
        f"  Failure modes: {len(failure_modes)}\n"
        f"  Total cells  : {total_cells}\n"
        f"{'='*60}"
    )

    for stack in stacks:
        t_ids = [t.id for t in stack]
        t_names = [t.name for t in stack]
        stack_label = " + ".join(t_ids)

        stack_result: Dict[str, Any] = {
            "technique_ids": t_ids,
            "technique_names": t_names,
            "failure_mode_results": [],
        }

        for failure_mode in failure_modes:
            done += 1
            cell_label = (
                f"P2 | [{stack_label}] × {failure_mode.id} "
                f"[{done}/{total_cells}]"
            )
            logger.info(f"\n{'─'*60}\n{cell_label}\n{'─'*60}")
            scenario = scenario_for_failure_mode(failure_mode)
            
            # Select the expert panel for this failure mode
            failure_mode_experts = experts_for_failure_mode(
                failure_mode, experts_by_domain, experts, config
            )

            # Single-technique medians for this failure mode
            fm_single_medians = {
                t.id: single_tech_medians.get((t.id, failure_mode.id))
                for t in stack
            }

            def _make_expert_coro(
                exp: ExpertProfile,
                rnd: int,
                prev: Optional[List],
                _stack=stack,
                _fm=failure_mode,
                _fm_medians=fm_single_medians,
            ):
                return expert_phase2_round(
                    expert=exp,
                    techniques=_stack,
                    failure_mode=_fm,
                    scenario=scenario,
                    round_num=rnd,
                    prev_round_responses=prev,
                    single_tech_medians=_fm_medians,
                    client=client,
                    semaphore=semaphore,
                    config=config,
                    prompts=prompts,
                )

            rounds_data, converged_at = await run_idea_cell(
                experts=failure_mode_experts,  # Use selected panel instead of global experts
                expert_coroutine_factory=_make_expert_coro,
                idea_rounds=aln.idea_rounds,
                convergence_threshold=aln.convergence_threshold,
                cell_label=cell_label,
            )

            agg = aggregate_final(rounds_data)

            fm_result: Dict[str, Any] = {
                "failure_mode_id": failure_mode.id,
                "failure_mode_name": failure_mode.name,
                "deployment_scenario_name": scenario.name,
                "rounds_data": rounds_data,
                "converged_at_round": converged_at,
                **agg,
            }
            stack_result["failure_mode_results"].append(fm_result)

            # Persist round-by-round to CSV
            for rd in rounds_data:
                append_rows_to_csv(
                    csv_path=run_info[f"round_{rd['round']}_csv_path"],
                    phase="phase2_defense_in_depth",
                    technique_ids=t_ids,
                    technique_names=t_names,
                    failure_mode=failure_mode,
                    round_num=rd["round"],
                    responses=rd["responses"],
                    run_id=run_info["run_id"],
                )

            est_str = f"{agg['estimate']:.3f}" if agg["estimate"] is not None else "N/A"
            logger.info(
                f"  ✓ {cell_label} → combined estimate = {est_str} incidents/year"
            )

        overall_results["phase2_results"].append(stack_result)
        save_json(run_info["json_path"], overall_results)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main orchestration entry point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_alignment_elicitation(
    client: Any,
    semaphore: SemaphoreType,
    config: AppConfig,
    input_data: AlignmentInputData,
) -> Dict[str, Any]:
    """
    Runs the full alignment failure-risk elicitation workflow.

    Args:
        client: Initialised async API client.
        semaphore: Concurrency limiter.
        config: Loaded alignment configuration.
        input_data: All pre-loaded alignment inputs.

    Returns:
        The full results dictionary (also written to disk during execution).
    """
    reset_token_counts()
    t0 = time.time()
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  Starting Alignment Failure-Risk Elicitation Workflow")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # ── Validate ──────────────────────────────────────────────────────────────
    if not input_data.experts:
        return {"error": "No experts loaded"}
    if not input_data.failure_modes:
        return {"error": "No failure modes loaded"}
    if not input_data.alignment_techniques:
        return {"error": "No alignment techniques loaded"}
    if not input_data.prompts:
        return {"error": "No prompts loaded"}

    # ── Initialise run ────────────────────────────────────────────────────────
    run_info = init_alignment_run(config)
    if run_info is None:
        return {"error": "Failed to initialise run directory"}

    aln = config.workflow_settings
    experts = input_data.experts
    techniques = input_data.alignment_techniques
    failure_modes = input_data.failure_modes

    logger.info(
        f"Run {run_info['run_id']}: "
        f"{len(experts)} experts, "
        f"{len(techniques)} techniques, "
        f"{len(failure_modes)} failure modes, "
        f"{aln.idea_rounds} Delphi rounds"
    )

    overall_results: Dict[str, Any] = {
        "run_metadata": {
            "run_id": run_info["run_id"],
            "timestamp_start": datetime.datetime.now().isoformat(),
            "config": {
                "provider": config.inferred_api_provider,
                "model": config.llm_settings.model,
                "temperature": config.llm_settings.temperature,
                "idea_rounds": aln.idea_rounds,
                "convergence_threshold": aln.convergence_threshold,
                "num_experts": len(experts),
                "num_techniques": len(techniques),
                "num_failure_modes": len(failure_modes),
                "run_defense_in_depth": aln.run_defense_in_depth,
                "run_technique_ranking": config.workflow_settings.technique_ranking_enabled,
                "compare_ranking_modes": config.workflow_settings.technique_ranking_enabled,
            },
            "scenario_resolution": "failure_mode_override_then_default",
        },
        "phase1_results": [],
        "technique_ranking_results": [],
        "technique_ranking_comparison_results": [],
        "phase2_results": [],
    }
    save_json(run_info["json_path"], overall_results)

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    try:
        single_tech_medians = await _run_phase1(
            experts=experts,
            techniques=techniques,
            failure_modes=failure_modes,
            client=client,
            semaphore=semaphore,
            config=config,
            prompts=input_data.prompts,
            run_info=run_info,
            overall_results=overall_results,
            experts_by_domain=input_data.experts_by_domain,  # Pass grouped experts
        )
    except Exception as exc:
        logger.error(f"Phase 1 failed: {exc}", exc_info=True)
        overall_results["error"] = f"Phase 1 crashed: {exc}"
        save_json(run_info["json_path"], overall_results)
        return overall_results

    # ── Phase 1B: Cross-technique ranking (additional run) ──────────────────
    try:
        await _run_phase1_technique_ranking(
            experts=experts,
            techniques=techniques,
            failure_modes=failure_modes,
            single_tech_medians=single_tech_medians,
            client=client,
            semaphore=semaphore,
            config=config,
            prompts=input_data.prompts,
            run_info=run_info,
            overall_results=overall_results,
            experts_by_domain=input_data.experts_by_domain,
        )
    except Exception as exc:
        logger.error(f"Phase 1B ranking failed: {exc}", exc_info=True)
        overall_results["phase1b_ranking_error"] = f"Phase 1B ranking crashed: {exc}"

    try:
        overall_results["technique_ranking_comparison_results"] = _compare_ranking_modes(
            run_info=run_info,
            overall_results=overall_results,
            techniques=techniques,
        )
        save_json(run_info["json_path"], overall_results)
    except Exception as exc:
        logger.error(f"Ranking comparison failed: {exc}", exc_info=True)
        overall_results["ranking_comparison_error"] = f"Ranking comparison crashed: {exc}"

    # ── Phase 2 (optional) ────────────────────────────────────────────────────
    if aln.run_defense_in_depth and len(techniques) >= 2:
        try:
            await _run_phase2(
                experts=experts,
                techniques=techniques,
                failure_modes=failure_modes,
                single_tech_medians=single_tech_medians,
                client=client,
                semaphore=semaphore,
                config=config,
                prompts=input_data.prompts,
                run_info=run_info,
                overall_results=overall_results,
                experts_by_domain=input_data.experts_by_domain,  # Pass grouped experts
            )
        except Exception as exc:
            logger.error(f"Phase 2 failed: {exc}", exc_info=True)
            overall_results["phase2_error"] = f"Phase 2 crashed: {exc}"
    elif aln.run_defense_in_depth and len(techniques) < 2:
        logger.warning(
            "Defense-in-depth requested but fewer than 2 techniques are active. "
            "Skipping Phase 2."
        )

    # ── Finalise ──────────────────────────────────────────────────────────────
    duration = time.time() - t0
    overall_results["run_metadata"]["timestamp_end"] = datetime.datetime.now().isoformat()
    overall_results["run_metadata"]["duration_seconds"] = round(duration, 2)

    token_usage = get_token_counts()
    overall_results["run_metadata"]["token_usage"] = token_usage
    logger.info(
        f"Token usage — Input: {token_usage['total_input_tokens']:,}, "
        f"Output: {token_usage['total_output_tokens']:,}, "
        f"Total: {token_usage['total_tokens']:,}"
    )

    save_json(run_info["json_path"], overall_results)
    update_registry(config, run_info["run_id"], run_info["run_dir"])

    # Generate plots automatically as part of the workflow run.
    try:
        ranking_plot_path = run_info["run_dir"] / "plots" / "technique_rankings.png"
        ranking_plot_result = plot_technique_ranking_summary(
            ranking_csv_path=run_info["ranking_csv_path"],
            output_png=ranking_plot_path,
        )
        if ranking_plot_result is not None:
            logger.info(f"Saved ranking plot: {ranking_plot_result}")

        ranking_comparison_plot_path = (
            run_info["run_dir"] / "plots" / "technique_ranking_comparison.png"
        )
        ranking_comparison_plot_result = plot_ranking_comparison_summary(
            ranking_comparison_csv_path=run_info["ranking_comparison_csv_path"],
            output_png=ranking_comparison_plot_path,
        )
        if ranking_comparison_plot_result is not None:
            logger.info(f"Saved ranking comparison plot: {ranking_comparison_plot_result}")

        def _safe_generate_phase_plots(phase_name: str) -> None:
            try:
                generate_plots(
                    run_id=run_info["run_id"],
                    phase=phase_name,
                    total_round_num=aln.idea_rounds,
                    runs_root=str(config.runs_dir),
                )
            except Exception as exc:
                if aln.idea_rounds is None:
                    logger.warning(f"Plot generation skipped for {phase_name} due to error: {exc}")
                else:
                    logger.warning(
                        f"Round-specific plot generation skipped for {phase_name}, "
                        f"round {aln.idea_rounds} due to error: {exc}"
                    )

        _safe_generate_phase_plots("phase1_single_technique")
        # if aln.idea_rounds >= 2:
        #     _safe_generate_phase_plots("phase1_single_technique", round_num=2)

        if aln.run_defense_in_depth and len(techniques) >= 2:
            _safe_generate_phase_plots("phase2_defense_in_depth")
            if aln.idea_rounds >= 2:
                _safe_generate_phase_plots("phase2_defense_in_depth", round_num=2)
    except Exception as exc:
        logger.warning(f"Plot generation skipped due to error: {exc}")

    logger.info(
        f"\n{'━'*60}\n"
        f"  Alignment elicitation completed in {duration:.1f}s\n"
        f"  Run ID : {run_info['run_id']}\n"
        f"  Output : {run_info['run_dir']}\n"
        f"{'━'*60}"
    )
    return overall_results
