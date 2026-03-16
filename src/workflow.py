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
import csv
import datetime
import json
import logging
import time
from dataclasses import asdict
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
)
from data_models import ExpertProfile
from llm_api import make_api_call, reset_token_counts, get_token_counts
from parsing import parse_failure_frequency_response, parse_defense_in_depth_response

logger = logging.getLogger(__name__)

# ── type aliases ─────────────────────────────────────────────────────────────
ClientType = Union["AsyncAnthropic", "AsyncOpenAI"]
SemaphoreType = asyncio.Semaphore


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Run initialisation / persistence helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _generate_run_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _init_alignment_run(config: AppConfig) -> Optional[Dict[str, Any]]:
    """
    Creates the output directory structure and initialises both the CSV and the
    JSON output files for a new run.

    Returns a dict with keys ``run_id``, ``run_dir``, ``csv_path``, ``json_path``,
    or ``None`` on failure.
    """
    run_id = _generate_run_id()
    run_dir: Path = config.runs_dir / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error(f"Cannot create run directory {run_dir}: {exc}")
        return None

    csv_path = run_dir / "detailed_estimates.csv"
    json_path = run_dir / "full_results.json"

    # Write CSV header
    header = [
        "run_id", "phase", "technique_ids", "technique_names",
        "failure_mode_id", "failure_mode_name",
        "round_num", "expert",
        "estimate", "minimum", "maximum", "confidence",
        "rationale", "key_assumptions", "error",
    ]
    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=header)
            writer.writeheader()
    except IOError as exc:
        logger.error(f"Cannot create CSV at {csv_path}: {exc}")
        return None

    logger.info(f"Alignment run initialised: {run_id}")
    logger.info(f"  CSV  : {csv_path}")
    logger.info(f"  JSON : {json_path}")
    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "csv_path": csv_path,
        "json_path": json_path,
    }


def _append_rows_to_csv(
    csv_path: Path,
    phase: str,
    technique_ids: List[str],
    technique_names: List[str],
    failure_mode: FailureMode,
    round_num: int,
    responses: List[Dict[str, Any]],
    run_id: str,
) -> None:
    """Appends one row per expert response to the CSV file."""
    header = [
        "run_id", "phase", "technique_ids", "technique_names",
        "failure_mode_id", "failure_mode_name",
        "round_num", "expert",
        "estimate", "minimum", "maximum", "confidence",
        "rationale", "key_assumptions", "error",
    ]
    try:
        with open(csv_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
            for resp in responses:
                writer.writerow(
                    {
                        "run_id": run_id,
                        "phase": phase,
                        "technique_ids": "|".join(technique_ids),
                        "technique_names": "|".join(technique_names),
                        "failure_mode_id": failure_mode.id,
                        "failure_mode_name": failure_mode.name,
                        "round_num": round_num,
                        "expert": resp.get("expert", ""),
                        "estimate": resp.get("estimate"),
                        "minimum": resp.get("minimum"),
                        "maximum": resp.get("maximum"),
                        "confidence": resp.get("confidence"),
                        "rationale": str(resp.get("rationale", "")),
                        "key_assumptions": str(resp.get("key_assumptions", "")),
                        "error": resp.get("error", ""),
                    }
                )
    except IOError as exc:
        logger.error(f"Error appending to CSV {csv_path}: {exc}")


def _save_json(json_path: Path, data: Dict[str, Any]) -> None:
    """Atomically saves the results dict as JSON."""
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
    except (IOError, TypeError) as exc:
        logger.error(f"Error saving JSON to {json_path}: {exc}")


def _update_registry(config: AppConfig, run_id: str, run_dir: Path) -> None:
    """Adds this run to the run_registry.json file."""
    registry_file = config.registry_file
    registry: Dict[str, Any] = {"runs": [], "last_updated": None}
    try:
        if registry_file.is_file():
            with open(registry_file, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
                if isinstance(loaded, dict):
                    registry = loaded
    except (json.JSONDecodeError, IOError):
        pass  # start fresh

    entry = {
        "run_id": run_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "output_path": str(run_dir),
        "study": "alignment",
        "provider": config.inferred_api_provider,
        "model": config.llm_settings.model,
    }
    if not isinstance(registry.get("runs"), list):
        registry["runs"] = []
    registry["runs"].insert(0, entry)
    registry["last_updated"] = datetime.datetime.now().isoformat()
    try:
        registry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(registry_file, "w", encoding="utf-8") as fh:
            json.dump(registry, fh, indent=2, ensure_ascii=False, default=str)
    except IOError as exc:
        logger.error(f"Cannot write registry {registry_file}: {exc}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Prompt building helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_system_prompt(
    expert: ExpertProfile,
    scenario: DeploymentScenario,
    prompts: Dict[str, str],
) -> str:
    """
    Builds the system prompt by combining the alignment ``system_context``
    template with the expert's persona description.
    """
    system_ctx_template = prompts.get("system_context", "")
    system_ctx = system_ctx_template.format(
        deployment_scenario_name=scenario.name,
        deployment_scenario_description=scenario.description,
        system_capability=scenario.system_capability,
        deployment_scale=scenario.scale,
        deployment_time_horizon=scenario.no_of_deployments,
        deployment_monitoring=scenario.monitoring_summary(),
        deployment_safety_assumptions=scenario.safety_assumptions_text(),
    ) if system_ctx_template else ""

    persona = expert.get_persona_description()
    return f"{system_ctx}\n\n{persona}".strip() if system_ctx else persona


def _baseline_for_failure_mode(
    failure_mode: FailureMode,
    scenario: DeploymentScenario,
) -> Tuple[float, float, float]:
    """
    Returns (mode, low, high) baseline incident frequencies.
    Prefers the scenario-level baseline; falls back to failure_mode-level baseline.
    """
    bi = scenario.baseline_incidents_per_year.get(failure_mode.id)
    if bi:
        return bi.mode, bi.low_5th_percentile, bi.high_95th_percentile
    # fallback: values embedded in the FailureMode object
    mode = failure_mode.baseline_mode or 0.0
    low = failure_mode.baseline_low or 0.0
    high = failure_mode.baseline_high or 0.0
    return mode, low, high


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Expert-level coroutines
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _expert_phase1_round(
    expert: ExpertProfile,
    technique: AlignmentTechnique,
    failure_mode: FailureMode,
    scenario: DeploymentScenario,
    round_num: int,
    prev_round_responses: Optional[List[Dict[str, Any]]],
    client: ClientType,
    semaphore: SemaphoreType,
    config: AppConfig,
    prompts: Dict[str, str],
) -> Dict[str, Any]:
    """
    Executes one expert's Phase-1 Delphi round for a given
    (technique, failure_mode) pair.
    """
    ename = expert.name
    expert_result: Dict[str, Any] = {
        "expert": ename,
        "estimate": None,
        "minimum": None,
        "maximum": None,
        "confidence": None,
        "rationale": "",
        "key_assumptions": "",
        "conditional_judgment": "",
    }

    system_prompt = _build_system_prompt(expert, scenario, prompts)
    # b_mode, b_low, b_high = _baseline_for_failure_mode(failure_mode, scenario)
    max_tokens = 8000

    common_data = dict(
        expert_name=expert.name,
        expert_background=expert.background,
        expert_focus=expert.focus,
        expert_key_trait=expert.key_trait,
        expert_bias=expert.bias,
        expert_analytical_approach=expert.analytical_approach or "N/A",
        expert_persona_description=expert.get_persona_description(),
        deployment_scenario_name=scenario.name,
        deployment_scenario_description=scenario.description,
        system_capability=scenario.system_capability,
        deployment_scale=scenario.scale,
        deployment_monitoring=scenario.monitoring_summary(),
        deployment_unit_name=scenario.deployment_unit_name,
        deployment_unit_description=scenario.deployment_unit_description,
        no_of_deployments=scenario.no_of_deployments,
        failure_mode_name=failure_mode.name,
        failure_mode_description=failure_mode.description,
        failure_mode_threat_model=failure_mode.threat_model,

        # baseline_frequency_mode=b_mode,
        # baseline_frequency_low=b_low,
        # baseline_frequency_high=b_high,
        technique_name=technique.name,
        technique_description=technique.description,
        technique_mechanism=technique.mechanism,
        technique_maturity_level=technique.maturity_level,
        technique_primary_failure_pathways=technique.failure_pathways_text(),
        technique_known_limitations=technique.known_limitations,
    )

    try:
        if round_num == 1:
            template = prompts.get("initial_failure_estimation")
            if not template:
                raise ValueError("Missing prompt: 'initial_failure_estimation'")
            user_prompt = template.format(**common_data)
            expert_result["user_prompt"] = user_prompt

            raw = await make_api_call(
                client, semaphore, config, system_prompt, user_prompt, max_tokens
            )
            expert_result["raw_response"] = raw
            if raw.startswith("Error:"):
                expert_result["error"] = f"API Error: {raw}"
                return expert_result

            parsed = parse_failure_frequency_response(raw)
            expert_result.update(parsed)
            if expert_result["estimate"] is None:
                expert_result["error"] = "Parsing failed: estimate is None"

        else:
            # ── Subsequent rounds ──────────────────────────────────────────
            if not prev_round_responses:
                expert_result["error"] = "No previous round data for refinement"
                return expert_result

            own_prev = next(
                (r for r in prev_round_responses
                 if r.get("expert") == ename and r.get("estimate") is not None
                 and "error" not in r),
                None,
            )
            if not own_prev:
                expert_result["error"] = f"No valid R{round_num-1} estimate to refine"
                return expert_result

            others_prev = [
                r for r in prev_round_responses
                if r.get("expert") != ename
                and r.get("estimate") is not None
                and "error" not in r
            ]

            context_lines = [
                f"--- Your Previous Estimate (Round {round_num - 1}) ---",
                f"Effect vs SFT: {own_prev.get('estimate', 'N/A')}%",
                f"Range: {own_prev.get('minimum', 'N/A')}% – {own_prev.get('maximum', 'N/A')}%",
                f"Causal rationale: {own_prev.get('rationale', 'N/A')}",
                "",
                f"--- Other Experts' Estimates (Round {round_num - 1}) ---",
            ]
            if others_prev:
                for r in others_prev:
                    short = str(r.get("rationale", "N/A"))[:200]
                    context_lines.append(
                        f"- {r['expert']}: {r.get('estimate', 'N/A')}% vs SFT | {short}"
                    )
            else:
                context_lines.append("(No other valid estimates in previous round)")
            context_lines.append("\n---")

            subsequent_data = dict(
                **common_data,
                round_num=round_num,
                prev_round_num=round_num - 1,
                context="\n".join(context_lines),
            )
            template = prompts.get("subsequent_failure_estimation")
            if not template:
                raise ValueError("Missing prompt: 'subsequent_failure_estimation'")

            user_prompt = template.format(**subsequent_data)
            expert_result["user_prompt"] = user_prompt

            raw = await make_api_call(
                client, semaphore, config, system_prompt, user_prompt, max_tokens
            )
            expert_result["raw_response"] = raw
            if raw.startswith("Error:"):
                expert_result["error"] = f"API Error: {raw}"
                return expert_result

            parsed = parse_failure_frequency_response(raw)
            expert_result.update(parsed)
            if expert_result["estimate"] is None:
                expert_result["error"] = "Parsing failed: estimate is None"

    except ValueError as exc:
        expert_result["error"] = f"Config/Prompt error: {exc}"
        logger.error(f"Phase1 R{round_num} — {ename} / {technique.id} × {failure_mode.id}: {exc}")
    except Exception as exc:
        expert_result["error"] = f"Unexpected error: {exc}"
        logger.error(
            f"Phase1 R{round_num} — {ename} / {technique.id} × {failure_mode.id}: {exc}",
            exc_info=True,
        )

    return expert_result


async def _expert_phase2_round(
    expert: ExpertProfile,
    techniques: List[AlignmentTechnique],   # 2 (or 3) techniques in the stack
    failure_mode: FailureMode,
    scenario: DeploymentScenario,
    round_num: int,
    prev_round_responses: Optional[List[Dict[str, Any]]],
    single_tech_medians: Dict[str, Optional[float]],  # technique_id → median
    client: ClientType,
    semaphore: SemaphoreType,
    config: AppConfig,
    prompts: Dict[str, str],
) -> Dict[str, Any]:
    """
    Executes one expert's Phase-2 (defense-in-depth) Delphi round.
    Currently supports stacks of exactly 2 techniques (pairs).
    """
    ename = expert.name
    expert_result: Dict[str, Any] = {
        "expert": ename,
        "estimate": None,
        "minimum": None,
        "maximum": None,
        "confidence": None,
        "rationale": "",
        "key_assumptions": "",
        "correlation_assessment": "",
        "residual_risk": "",
    }

    if len(techniques) < 2:
        expert_result["error"] = "Phase 2 requires at least 2 techniques"
        return expert_result

    t1, t2 = techniques[0], techniques[1]
    system_prompt = _build_system_prompt(expert, scenario, prompts)
    # b_mode, b_low, b_high = _baseline_for_failure_mode(failure_mode, scenario)
    max_tokens = 8000

    t1_single = single_tech_medians.get(t1.id)
    t2_single = single_tech_medians.get(t2.id)
    t1_single_str = f"{t1_single:.2f}" if t1_single is not None else "N/A"
    t2_single_str = f"{t2_single:.2f}" if t2_single is not None else "N/A"

    common_data = dict(
        expert_name=expert.name,
        expert_background=expert.background,
        expert_focus=expert.focus,
        expert_key_trait=expert.key_trait,
        expert_bias=expert.bias,
        expert_persona_description=expert.get_persona_description(),
        deployment_scenario_name=scenario.name,
        deployment_scenario_description=scenario.description,
        system_capability=scenario.system_capability,
        failure_mode_name=failure_mode.name,
        failure_mode_description=failure_mode.description,
        deployment_unit_name="task runs",
        deployment_unit_definition="One task run = one complete execution of the agent's assigned goal in the described deployment context (from task assignment to final output). Each run is independent.",
        # baseline_frequency_mode=b_mode,
        # baseline_frequency_low=b_low,
        # baseline_frequency_high=b_high,
        technique_1_name=t1.name,
        technique_1_mechanism=t1.mechanism,
        technique_1_primary_failure_pathways=t1.failure_pathways_text(),
        technique_1_single_estimate=t1_single_str,
        technique_2_name=t2.name,
        technique_2_mechanism=t2.mechanism,
        technique_2_primary_failure_pathways=t2.failure_pathways_text(),
        technique_2_single_estimate=t2_single_str,
    )

    try:
        if round_num == 1:
            template = prompts.get("defense_in_depth_initial")
            if not template:
                raise ValueError("Missing prompt: 'defense_in_depth_initial'")
            user_prompt = template.format(**common_data)
            expert_result["user_prompt"] = user_prompt

            raw = await make_api_call(
                client, semaphore, config, system_prompt, user_prompt, max_tokens
            )
            expert_result["raw_response"] = raw
            if raw.startswith("Error:"):
                expert_result["error"] = f"API Error: {raw}"
                return expert_result

            parsed = parse_defense_in_depth_response(raw)
            expert_result.update(parsed)
            if expert_result["estimate"] is None:
                expert_result["error"] = "Parsing failed: estimate is None"

        else:
            if not prev_round_responses:
                expert_result["error"] = "No previous round data for DID refinement"
                return expert_result

            own_prev = next(
                (r for r in prev_round_responses
                 if r.get("expert") == ename and r.get("estimate") is not None
                 and "error" not in r),
                None,
            )
            if not own_prev:
                expert_result["error"] = f"No valid R{round_num-1} estimate to refine"
                return expert_result

            others_prev = [
                r for r in prev_round_responses
                if r.get("expert") != ename
                and r.get("estimate") is not None
                and "error" not in r
            ]

            context_lines = [
                f"--- Your Previous Estimate (Round {round_num - 1}) ---",
                f"Estimated combined frequency: {own_prev.get('estimate', 'N/A')} incidents/year",
                f"Correlation assessment: {own_prev.get('correlation_assessment', 'N/A')}",
                f"Rationale: {str(own_prev.get('rationale', 'N/A'))[:200]}",
                "",
                f"--- Other Experts (Round {round_num - 1}) ---",
            ]
            if others_prev:
                for r in others_prev:
                    context_lines.append(
                        f"- {r['expert']}: {r.get('estimate', 'N/A')} inc/yr | "
                        f"correlation: {r.get('correlation_assessment', 'N/A')}"
                    )
            else:
                context_lines.append("(No other valid estimates)")
            context_lines.append("\n---")

            subsequent_data = dict(
                **common_data,
                round_num=round_num,
                prev_round_num=round_num - 1,
                context="\n".join(context_lines),
            )
            template = prompts.get("defense_in_depth_subsequent")
            if not template:
                raise ValueError("Missing prompt: 'defense_in_depth_subsequent'")

            user_prompt = template.format(**subsequent_data)
            expert_result["user_prompt"] = user_prompt

            raw = await make_api_call(
                client, semaphore, config, system_prompt, user_prompt, max_tokens
            )
            expert_result["raw_response"] = raw
            if raw.startswith("Error:"):
                expert_result["error"] = f"API Error: {raw}"
                return expert_result

            parsed = parse_defense_in_depth_response(raw)
            expert_result.update(parsed)
            if expert_result["estimate"] is None:
                expert_result["error"] = "Parsing failed: estimate is None"

    except ValueError as exc:
        expert_result["error"] = f"Config/Prompt error: {exc}"
        logger.error(f"Phase2 R{round_num} — {ename}: {exc}")
    except Exception as exc:
        expert_result["error"] = f"Unexpected error: {exc}"
        logger.error(f"Phase2 R{round_num} — {ename}: {exc}", exc_info=True)

    return expert_result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Task-level Delphi helpers (reusable for both phases)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _run_delphi_cell(
    experts: List[ExpertProfile],
    expert_coroutine_factory: Callable[[ExpertProfile, int, Optional[List]], Any],
    delphi_rounds: int,
    convergence_threshold: float,
    cell_label: str,
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """
    Generic Delphi loop for a single elicitation cell.

    Args:
        experts: List of expert personas.
        expert_coroutine_factory: A callable ``f(expert, round_num, prev_responses)``
            that returns an awaitable producing a per-expert result dict.
        delphi_rounds: Maximum rounds to run.
        convergence_threshold: Stop early when std-dev of estimates < this threshold.
        cell_label: Human-readable label used in log messages.

    Returns:
        (all_round_data, converged_at_round)
        all_round_data: list of per-round dicts
            ``{"round": int, "responses": [per-expert-dict]}``
    """
    all_round_data: List[Dict[str, Any]] = []
    history: List[List[Dict[str, Any]]] = []
    converged_at: Optional[int] = None

    for r in range(1, delphi_rounds + 1):
        t0 = time.time()
        logger.info(f"  [{cell_label}] Round {r}/{delphi_rounds} starting…")
        prev = history[-1] if history else None

        tasks = [expert_coroutine_factory(exp, r, prev) for exp in experts]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        responses: List[Dict[str, Any]] = []
        for i, res in enumerate(raw_results):
            exp_name = experts[i].name
            if isinstance(res, Exception):
                logger.error(f"    Expert '{exp_name}' R{r} failed: {res}", exc_info=res)
                responses.append({"expert": exp_name, "error": str(res)})
            else:
                responses.append(res)

        history.append(responses)
        all_round_data.append({"round": r, "responses": responses})
        logger.info(f"  [{cell_label}] Round {r} done in {time.time()-t0:.1f}s")

        valid_estimates = [
            r_["estimate"] for r_ in responses
            if "error" not in r_ and r_.get("estimate") is not None
        ]
        if len(valid_estimates) >= 2:
            std_dev = float(np.std(valid_estimates))
            mean_est = float(np.mean(valid_estimates))
            logger.info(
                f"    Stats: n={len(valid_estimates)}, "
                f"mean={mean_est:.3f}, std={std_dev:.3f}"
            )
            if std_dev < convergence_threshold:
                logger.info(
                    f"    Convergence at R{r} "
                    f"(std={std_dev:.3f} < threshold={convergence_threshold})"
                )
                converged_at = r
                break
        else:
            logger.info(
                f"    Not enough valid estimates ({len(valid_estimates)}) "
                "to test convergence."
            )

    return all_round_data, converged_at


def _aggregate_final(
    rounds_data: List[Dict[str, Any]],
) -> Dict[str, Optional[float]]:
    """
    Returns the mean of each numeric estimate field from the *last* round.
    """
    if not rounds_data:
        return {"estimate": None, "minimum": None, "maximum": None, "confidence": None}

    final_responses = rounds_data[-1]["responses"]
    valid = [r for r in final_responses if "error" not in r and r.get("estimate") is not None]
    if not valid:
        return {"estimate": None, "minimum": None, "maximum": None, "confidence": None}

    def _mean(key: str) -> Optional[float]:
        vals = [r[key] for r in valid if r.get(key) is not None]
        return float(np.mean(vals)) if vals else None

    return {
        "estimate": _mean("estimate"),
        "minimum": _mean("minimum"),
        "maximum": _mean("maximum"),
        "confidence": _mean("confidence"),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase runners
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _run_phase1(
    experts: List[ExpertProfile],
    techniques: List[AlignmentTechnique],
    failure_modes: List[FailureMode],
    scenario: DeploymentScenario,
    client: ClientType,
    semaphore: SemaphoreType,
    config: AppConfig,
    prompts: Dict[str, str],
    run_info: Dict[str, Any],
    overall_results: Dict[str, Any],
) -> Dict[Tuple[str, str], Optional[float]]:
    """
    Phase 1: Delphi estimation for every (technique × failure_mode) pair.

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

            def _make_expert_coro(
                exp: ExpertProfile,
                rnd: int,
                prev: Optional[List],
                _tech=technique,
                _fm=failure_mode,
            ):
                return _expert_phase1_round(
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
                )

            rounds_data, converged_at = await _run_delphi_cell(
                experts=experts,
                expert_coroutine_factory=_make_expert_coro,
                delphi_rounds=aln.delphi_rounds,
                convergence_threshold=aln.convergence_threshold,
                cell_label=cell_label,
            )

            agg = _aggregate_final(rounds_data)
            single_tech_medians[(technique.id, failure_mode.id)] = agg["estimate"]

            fm_result: Dict[str, Any] = {
                "failure_mode_id": failure_mode.id,
                "failure_mode_name": failure_mode.name,
                "rounds_data": rounds_data,
                "converged_at_round": converged_at,
                **agg,
            }
            # tech_result_entry is the same dict object already in overall_results
            tech_result_entry["failure_mode_results"].append(fm_result)

            # Persist round-by-round to CSV
            for rd in rounds_data:
                _append_rows_to_csv(
                    csv_path=run_info["csv_path"],
                    phase="phase1_single_technique",
                    technique_ids=[technique.id],
                    technique_names=[technique.name],
                    failure_mode=failure_mode,
                    round_num=rd["round"],
                    responses=rd["responses"],
                    run_id=run_info["run_id"],
                )

            # Snapshot JSON after each cell
            _save_json(run_info["json_path"], overall_results)

            est_str = f"{agg['estimate']:.3f}" if agg["estimate"] is not None else "N/A"
            logger.info(
                f"  ✓ {cell_label} → final estimate = {est_str} incidents/year"
            )

        # Technique complete – final snapshot already written in inner loop
        _save_json(run_info["json_path"], overall_results)

    return single_tech_medians


async def _run_phase2(
    experts: List[ExpertProfile],
    techniques: List[AlignmentTechnique],
    failure_modes: List[FailureMode],
    scenario: DeploymentScenario,
    single_tech_medians: Dict[Tuple[str, str], Optional[float]],
    client: ClientType,
    semaphore: SemaphoreType,
    config: AppConfig,
    prompts: Dict[str, str],
    run_info: Dict[str, Any],
    overall_results: Dict[str, Any],
) -> None:
    """
    Phase 2: Defense-in-depth Delphi for technique combinations.
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
                return _expert_phase2_round(
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

            rounds_data, converged_at = await _run_delphi_cell(
                experts=experts,
                expert_coroutine_factory=_make_expert_coro,
                delphi_rounds=aln.delphi_rounds,
                convergence_threshold=aln.convergence_threshold,
                cell_label=cell_label,
            )

            agg = _aggregate_final(rounds_data)

            fm_result: Dict[str, Any] = {
                "failure_mode_id": failure_mode.id,
                # "failure_mode_name": failure_mode.name,
                "rounds_data": rounds_data,
                "converged_at_round": converged_at,
                **agg,
            }
            stack_result["failure_mode_results"].append(fm_result)

            # Persist round-by-round to CSV
            for rd in rounds_data:
                _append_rows_to_csv(
                    csv_path=run_info["csv_path"],
                    phase="phase2_defense_in_depth",
                    technique_ids=t_ids,
                    # technique_names=t_names,
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
        _save_json(run_info["json_path"], overall_results)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main orchestration entry point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_alignment_elicitation(
    client: ClientType,
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
    run_info = _init_alignment_run(config)
    if run_info is None:
        return {"error": "Failed to initialise run directory"}

    aln = config.workflow_settings
    experts = input_data.experts
    techniques = input_data.alignment_techniques
    failure_modes = input_data.failure_modes
    scenario = input_data.deployment_scenario

    logger.info(
        f"Run {run_info['run_id']}: "
        f"{len(experts)} experts, "
        f"{len(techniques)} techniques, "
        f"{len(failure_modes)} failure modes, "
        f"{aln.delphi_rounds} Delphi rounds"
    )

    overall_results: Dict[str, Any] = {
        "run_metadata": {
            "run_id": run_info["run_id"],
            "timestamp_start": datetime.datetime.now().isoformat(),
            "config": {
                "provider": config.inferred_api_provider,
                "model": config.llm_settings.model,
                "temperature": config.llm_settings.temperature,
                "delphi_rounds": aln.delphi_rounds,
                "convergence_threshold": aln.convergence_threshold,
                "num_experts": len(experts),
                "num_techniques": len(techniques),
                "num_failure_modes": len(failure_modes),
                "run_defense_in_depth": aln.run_defense_in_depth,
            },
            "deployment_scenario": scenario.name,
        },
        "phase1_results": [],
        "phase2_results": [],
    }
    _save_json(run_info["json_path"], overall_results)

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    try:
        single_tech_medians = await _run_phase1(
            experts=experts,
            techniques=techniques,
            failure_modes=failure_modes,
            scenario=scenario,
            client=client,
            semaphore=semaphore,
            config=config,
            prompts=input_data.prompts,
            run_info=run_info,
            overall_results=overall_results,
        )
    except Exception as exc:
        logger.error(f"Phase 1 failed: {exc}", exc_info=True)
        overall_results["error"] = f"Phase 1 crashed: {exc}"
        _save_json(run_info["json_path"], overall_results)
        return overall_results

    # ── Phase 2 (optional) ────────────────────────────────────────────────────
    if aln.run_defense_in_depth and len(techniques) >= 2:
        try:
            await _run_phase2(
                experts=experts,
                techniques=techniques,
                failure_modes=failure_modes,
                scenario=scenario,
                single_tech_medians=single_tech_medians,
                client=client,
                semaphore=semaphore,
                config=config,
                prompts=input_data.prompts,
                run_info=run_info,
                overall_results=overall_results,
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

    _save_json(run_info["json_path"], overall_results)
    _update_registry(config, run_info["run_id"], run_info["run_dir"])

    logger.info(
        f"\n{'━'*60}\n"
        f"  Alignment elicitation completed in {duration:.1f}s\n"
        f"  Run ID : {run_info['run_id']}\n"
        f"  Output : {run_info['run_dir']}\n"
        f"{'━'*60}"
    )
    return overall_results
