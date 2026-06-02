
import csv
import json
import datetime
import logging
from pathlib import Path

from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from config import AppConfig
from data_models import (
    DeploymentScenario,
    FailureMode,
)

logger = logging.getLogger(__name__)


def _generate_run_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def init_alignment_run(config: AppConfig) -> Optional[Dict[str, Any]]:
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

    round_1_csv_path = run_dir / f"round_1_detailed_estimates.csv"
    round_2_csv_path = run_dir / f"round_2_detailed_estimates.csv"
    json_path = run_dir / "full_results.json"
    ranking_csv_path = run_dir / "technique_rankings.csv"
    ranking_comparison_csv_path = run_dir / "technique_ranking_comparison.csv"

    # Write CSV header
    header = [
        "run_id", "phase", "technique_ids", "technique_names",
        "failure_mode_id", "failure_mode_name",
        "round_num", "expert",
        "estimate", "minimum", "maximum", "confidence",
        "rationale", "key_assumptions", "error",
    ]
    try:
        with open(round_1_csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=header)
            writer.writeheader()
        with open(round_2_csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=header)
            writer.writeheader()
    except IOError as exc:
        logger.error(f"Cannot create CSV at {round_1_csv_path} and {round_2_csv_path}: {exc}")
        return None

    ranking_header = [
        "run_id",
        "failure_mode_id",
        "failure_mode_name",
        "deployment_scenario_name",
        "expert",
        "rank",
        "technique_id",
        "technique_name",
        "reduction_pct_vs_sft",
        "rationale",
        "error",
    ]
    try:
        with open(ranking_csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=ranking_header)
            writer.writeheader()
    except IOError as exc:
        logger.error(f"Cannot create ranking CSV at {ranking_csv_path}: {exc}")
        return None

    ranking_comparison_header = [
        "run_id",
        "failure_mode_id",
        "failure_mode_name",
        "deployment_scenario_name",
        "expert",
        "technique_id",
        "technique_name",
        "one_by_one_estimate",
        "one_by_one_rank",
        "all_at_once_reduction_pct_vs_sft",
        "all_at_once_rank",
        "rank_diff",
        "abs_rank_diff",
        "error",
    ]
    try:
        with open(ranking_comparison_csv_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=ranking_comparison_header)
            writer.writeheader()
    except IOError as exc:
        logger.error(
            f"Cannot create ranking comparison CSV at {ranking_comparison_csv_path}: {exc}"
        )
        return None

    logger.info(f"Alignment run initialised: {run_id}")
    logger.info(f"  CSV  : {round_1_csv_path} and {round_2_csv_path}")
    logger.info(f"  JSON : {json_path}")
    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "round_1_csv_path": round_1_csv_path,
        "round_2_csv_path": round_2_csv_path,
        "json_path": json_path,
        "ranking_csv_path": ranking_csv_path,
        "ranking_comparison_csv_path": ranking_comparison_csv_path,
    }


def append_rows_to_csv(
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


def append_ranking_rows_to_csv(
    ranking_csv_path: Path,
    run_id: str,
    failure_mode: FailureMode,
    scenario: DeploymentScenario,
    expert_result: Dict[str, Any],
    technique_name_by_id: Dict[str, str],
) -> None:
    """Appends one expert's ranking response to the dedicated ranking CSV."""
    header = [
        "run_id",
        "failure_mode_id",
        "failure_mode_name",
        "deployment_scenario_name",
        "expert",
        "rank",
        "technique_id",
        "technique_name",
        "reduction_pct_vs_sft",
        "rationale",
        "error",
    ]

    try:
        with open(ranking_csv_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")

            rankings = expert_result.get("rankings") or []
            if rankings:
                for row in rankings:
                    tid = str(row.get("technique_id", ""))
                    writer.writerow(
                        {
                            "run_id": run_id,
                            "failure_mode_id": failure_mode.id,
                            "failure_mode_name": failure_mode.name,
                            "deployment_scenario_name": scenario.name,
                            "expert": expert_result.get("expert", ""),
                            "rank": row.get("rank"),
                            "technique_id": tid,
                            "technique_name": technique_name_by_id.get(tid, tid),
                            "reduction_pct_vs_sft": row.get("reduction_pct"),
                            "rationale": str(expert_result.get("rationale", "")),
                            "error": "",
                        }
                    )
            else:
                writer.writerow(
                    {
                        "run_id": run_id,
                        "failure_mode_id": failure_mode.id,
                        "failure_mode_name": failure_mode.name,
                        "deployment_scenario_name": scenario.name,
                        "expert": expert_result.get("expert", ""),
                        "rank": "",
                        "technique_id": "",
                        "technique_name": "",
                        "reduction_pct_vs_sft": "",
                        "rationale": str(expert_result.get("rationale", "")),
                        "error": str(expert_result.get("error", "Unknown ranking error")),
                    }
                )
    except IOError as exc:
        logger.error(f"Error appending to ranking CSV {ranking_csv_path}: {exc}")


def append_ranking_comparison_rows_to_csv(
    ranking_comparison_csv_path: Path,
    rows: List[Dict[str, Any]],
) -> None:
    """Appends all-at-once vs one-by-one ranking comparison rows to CSV."""
    header = [
        "run_id",
        "failure_mode_id",
        "failure_mode_name",
        "deployment_scenario_name",
        "expert",
        "technique_id",
        "technique_name",
        "one_by_one_estimate",
        "one_by_one_rank",
        "all_at_once_reduction_pct_vs_sft",
        "all_at_once_rank",
        "rank_diff",
        "abs_rank_diff",
        "error",
    ]

    try:
        with open(ranking_comparison_csv_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
            writer.writerows(rows)
    except IOError as exc:
        logger.error(
            f"Error appending to ranking comparison CSV {ranking_comparison_csv_path}: {exc}"
        )


def save_json(json_path: Path, data: Dict[str, Any]) -> None:
    """Atomically saves the results dict as JSON."""
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
    except (IOError, TypeError) as exc:
        logger.error(f"Error saving JSON to {json_path}: {exc}")


def update_registry(config: AppConfig, run_id: str, run_dir: Path) -> None:
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

