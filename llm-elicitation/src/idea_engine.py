import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from config import AppConfig
from data_models import (
    AlignmentTechnique,
    DeploymentScenario,
    FailureMode,
    ExpertProfile
)
from llm_api import (
    make_api_call
)
from parsing import (
    parse_failure_frequency_response,
    parse_defense_in_depth_response,
    parse_technique_ranking_response,
)
from prompt_builders import build_system_prompt

logger = logging.getLogger(__name__)
SemaphoreType = asyncio.Semaphore

async def run_idea_cell(
    experts: List[ExpertProfile],
    expert_coroutine_factory: Callable[[ExpertProfile, int, Optional[List]], Any],
    idea_rounds: int,
    convergence_threshold: float,
    cell_label: str,
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    """
    Generic Delphi loop for a single elicitation cell.

    Args:
        experts: List of expert personas.
        expert_coroutine_factory: A callable ``f(expert, round_num, prev_responses)``
            that returns an awaitable producing a per-expert result dict.
        idea_rounds: Maximum rounds to run.
        convergence_threshold: Kept for backward compatibility; no early stop is applied.
        cell_label: Human-readable label used in log messages.

    Returns:
        (all_round_data, converged_at_round)
        all_round_data: list of per-round dicts
            ``{"round": int, "responses": [per-expert-dict]}``
    """
    all_round_data: List[Dict[str, Any]] = []
    history: List[List[Dict[str, Any]]] = []
    converged_at: Optional[int] = None

    for r in range(1, idea_rounds + 1):
        t0 = time.time()
        logger.info(f"  [{cell_label}] Round {r}/{idea_rounds} starting…")
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
        if len(valid_estimates) >= 1:
            std_dev = float(np.std(valid_estimates)) if len(valid_estimates) >= 2 else 0.0
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


def aggregate_final(
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


async def expert_phase1_round(
    expert: ExpertProfile,
    technique: AlignmentTechnique,
    failure_mode: FailureMode,
    scenario: DeploymentScenario,
    round_num: int,
    prev_round_responses: Optional[List[Dict[str, Any]]],
    client: Any,
    semaphore: SemaphoreType,
    config: AppConfig,
    prompts: Dict[str, str],
    technique_file_context: Optional[str] = None,
    technique_context_cache: Optional[Dict[Tuple[str, str], str]] = None,
) -> Dict[str, Any]:
    """
    Executes one expert's Phase-1 Delphi round for a given
    (technique, failure_mode) pair.
    
    Args:
        expert: The expert profile
        technique: The alignment technique
        failure_mode: The failure mode
        scenario: The deployment scenario
        round_num: Delphi round number
        prev_round_responses: Previous round responses for refinement
        client: LLM API client
        semaphore: Async semaphore for rate limiting
        config: Application configuration
        prompts: Prompt templates
        technique_file_context: Pre-computed technique context (for backward compatibility)
        technique_context_cache: Dict mapping (technique_id, expert_name) → context
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
    
    # Resolve technique context: prefer cache over parameter
    resolved_context = technique_file_context or ""
    if technique_context_cache is not None:
        cache_key = (technique.id, ename)
        resolved_context = technique_context_cache.get(cache_key, resolved_context)

    system_prompt = build_system_prompt(expert, scenario, prompts)
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
        technique_name=technique.name,
        technique_description=technique.description,
        technique_mechanism=technique.mechanism,
        technique_maturity_level=technique.maturity_level,
        technique_primary_failure_pathways=technique.failure_pathways_text(),
        technique_known_limitations=technique.known_limitations,
        technique_file_context=resolved_context,
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
                total_estimate = own_prev.get("estimate", 0)
                count_estimate = 1 if own_prev.get("estimate") is not None else 0
                for r in others_prev:
                    rationale = str(r.get("rationale", "N/A"))
                    print(f"length of rationale: {len(rationale)}")
                    context_lines.append(
                        f"- {r['expert']}: {r.get('estimate', 'N/A')}% reduction vs SFT | {rationale}"
                    )
                    total_estimate += r.get("estimate", 0)
                    count_estimate += 1
                avg_estimate = total_estimate / count_estimate if count_estimate > 0 else "N/A"
                context_lines.append(f"\n\nAverage of all estimates: {avg_estimate:.3f}% reduction vs SFT")
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


async def expert_phase2_round(
    expert: ExpertProfile,
    techniques: List[AlignmentTechnique],   # 2 (or 3) techniques in the stack
    failure_mode: FailureMode,
    scenario: DeploymentScenario,
    round_num: int,
    prev_round_responses: Optional[List[Dict[str, Any]]],
    single_tech_medians: Dict[str, Optional[float]],  # technique_id → median
    client: Any,
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
    system_prompt = build_system_prompt(expert, scenario, prompts)
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
                f"Rationale: {str(own_prev.get('rationale', 'N/A'))}",
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


async def expert_technique_ranking(
    expert: ExpertProfile,
    techniques: List[AlignmentTechnique],
    failure_mode: FailureMode,
    scenario: DeploymentScenario,
    per_technique_estimate_context: str,
    client: Any,
    semaphore: SemaphoreType,
    config: AppConfig,
    prompts: Dict[str, str],
) -> Dict[str, Any]:
    """Collects one expert's ranking of all techniques for one failure mode."""
    expert_result: Dict[str, Any] = {
        "expert": expert.name,
        "rankings": [],
        "rationale": "",
        "error": None,
    }

    system_prompt = build_system_prompt(expert, scenario, prompts)
    max_tokens = 8000

    technique_lines: List[str] = []
    for idx, tech in enumerate(techniques, start=1):
        short_desc = (tech.description or "").strip().replace("\n", " ")
        short_mech = (tech.mechanism or "").strip().replace("\n", " ")
        # if len(short_desc) > 240:
        #     short_desc = short_desc[:240] + "..."
        # if len(short_mech) > 240:
        #     short_mech = short_mech[:240] + "..."
        technique_lines.append(
            f"{idx}. {tech.name} (id={tech.id})\n"
            f"   Description: {short_desc}\n"
            f"   Mechanism: {short_mech}\n"
            f"   Known limitations: {tech.known_limitations}"
        )

    template = prompts.get("alignment_technique_ranking")
    user_prompt = template.format(
        expert_name=expert.name,
        expert_background=expert.background,
        expert_focus=expert.focus,
        expert_key_trait=expert.key_trait,
        expert_bias=expert.bias,
        deployment_scenario_name=scenario.name,
        deployment_scenario_description=scenario.description,
        system_capability=scenario.system_capability,
        failure_mode_name=failure_mode.name,
        failure_mode_description=failure_mode.description,
        failure_mode_threat_model=failure_mode.threat_model,
        techniques_block="\n\n".join(technique_lines),
        phase1_estimate_context=per_technique_estimate_context,
    )

    try:
        raw = await make_api_call(
            client,
            semaphore,
            config,
            system_prompt,
            user_prompt,
            max_tokens,
        )
        expert_result["raw_response"] = raw
        if raw.startswith("Error:"):
            expert_result["error"] = f"API Error: {raw}"
            return expert_result

        parsed = parse_technique_ranking_response(
            raw,
            expected_technique_ids=[t.id for t in techniques],
        )
        expert_result["rankings"] = parsed.get("rankings", [])
        expert_result["rationale"] = parsed.get("rationale", "")
        expert_result["error"] = parsed.get("error")
        if not expert_result["rankings"] and not expert_result["error"]:
            expert_result["error"] = "Parsing failed: rankings empty"
    except Exception as exc:
        expert_result["error"] = f"Unexpected error: {exc}"
        logger.error(
            "Technique ranking failed for expert '%s' and failure mode '%s': %s",
            expert.name,
            failure_mode.id,
            exc,
            exc_info=True,
        )

    return expert_result

