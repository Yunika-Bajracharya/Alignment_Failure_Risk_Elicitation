# src/data_loader.py
"""
Data-loading functions for the AI alignment failure-risk elicitation study.

Loads:
  - Expert profiles     (data_loader.load_experts)
  - Prompt templates    (data_loader.load_prompts)
  - Deployment scenario (input_data/deployment_scenario.yaml)
  - Failure modes       (input_data/failure_modes.yaml)
  - Alignment techniques (input_data/alignment_techniques.yaml)"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from config import AppConfig
from data_models import (
    AlignmentInputData,
    AlignmentTechnique,
    # BaselineIncident,
    ExpertProfile,
    ExpertsByDomain,
    DeploymentScenario,
    FailureMode,
)

logger = logging.getLogger(__name__)

# --- Data Loading Functions ---


def _parse_deployment_scenario_record(
    raw_scenario: Dict[str, Any],
    *,
    fallback_name: str = "Unnamed Scenario",
) -> DeploymentScenario:
    """Builds a ``DeploymentScenario`` from either nested or flat YAML layouts."""
    ctx = raw_scenario.get("deployment_context", {}) or {}
    if not isinstance(ctx, dict):
        ctx = {}

    mon = raw_scenario.get("monitoring_and_oversight", {}) or {}
    if not isinstance(mon, dict):
        mon = {}

    safety_assumptions = raw_scenario.get("safety_assumptions", []) or []
    if not isinstance(safety_assumptions, list):
        safety_assumptions = [str(safety_assumptions)]

    return DeploymentScenario(
        name=str(raw_scenario.get("name", fallback_name)),
        description=str(raw_scenario.get("description", "")),
        system_capability=str(raw_scenario.get("system_capability", "")),
        scale=str(ctx.get("scale", raw_scenario.get("scale", ""))),
        operator_type=str(ctx.get("operator_type", raw_scenario.get("operator_type", ""))),
        user_type=str(ctx.get("user_type", raw_scenario.get("user_type", ""))),
        deployment_unit_name=str(
            ctx.get(
                "deployment_unit_name",
                raw_scenario.get("deployment_unit_name", "task run"),
            )
        ),
        deployment_unit_description=str(
            ctx.get(
                "deployment_unit_description",
                raw_scenario.get(
                    "deployment_unit_description",
                    "one complete execution of the agent's assigned goal from task assignment to final output",
                ),
            )
        ),
        no_of_deployments=str(
            ctx.get("no_of_deployments", raw_scenario.get("no_of_deployments", ""))
        ),
        access_scope=str(ctx.get("access_scope", raw_scenario.get("access_scope", ""))),
        logging_policy=str(
            mon.get(
                "logging",
                raw_scenario.get("logging_policy", raw_scenario.get("logging_system", "")),
            )
        ),
        human_review=str(mon.get("human_review", raw_scenario.get("human_review", ""))),
        intervention_capability=str(
            mon.get(
                "intervention_capability",
                raw_scenario.get("intervention_capability", ""),
            )
        ),
        update_cycle=str(
            mon.get(
                "update_cycle",
                raw_scenario.get("update_cycle", raw_scenario.get("investigation_trigger", "")),
            )
        ),
        safety_assumptions=[str(a) for a in safety_assumptions],
    )

def load_prompts(prompts_dir: Path) -> Dict[str, str]:
    """
    Loads all .txt prompt files from the specified directory.

    Args:
        prompts_dir: The Path object pointing to the directory containing prompt files.

    Returns:
        A dictionary where keys are prompt filenames (without extension)
        and values are the content of the files. Returns an empty dict if
        the directory doesn't exist or no .txt files are found.
    """
    prompts: Dict[str, str] = {}
    if not prompts_dir.is_dir():
        logger.error(f"Prompts directory not found or is not a directory: {prompts_dir}")
        return prompts

    try:
        for prompt_file in prompts_dir.glob('*.txt'):
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompts[prompt_file.stem] = f.read()
            except IOError as e:
                logger.warning(f"Could not read prompt file {prompt_file.name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error reading prompt file {prompt_file.name}: {e}", exc_info=True)

        if not prompts:
            logger.warning(f"No .txt prompt files found in directory: {prompts_dir}")
        else:
            logger.info(f"Loaded {len(prompts)} prompts from {prompts_dir}")


    except Exception as e:
        logger.error(f"Error scanning prompts directory {prompts_dir}: {e}", exc_info=True)

    return prompts


def load_experts(expert_file: Path) -> List[ExpertProfile]:
    """
    Loads expert persona definitions from the specified YAML file.
    
    Supports two formats:
    1. Domain-grouped format (NEW):
       ai_safety:
         - name: "Expert Name"
           ...
       biosecurity:
         - name: "Expert Name"
           ...
    
    2. Flat format (legacy):
       experts:
         - name: "Expert Name"
           ...

    Args:
        expert_file: The Path object pointing to the expert profiles YAML file.

    Returns:
        A list of ExpertProfile objects. Returns an empty list if the file
        cannot be read, parsed, or contains invalid data.
    """
    expert_profiles: List[ExpertProfile] = []
    if not expert_file.is_file():
        logger.error(f"Expert profiles file not found: {expert_file}")
        return expert_profiles

    try:
        with open(expert_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            logger.error(f"Invalid format in expert file {expert_file.name}. Expected a dictionary at top level.")
            return expert_profiles

        # Try new domain-grouped format first
        expert_profiles = _load_experts_from_grouped_yaml(data, expert_file)
        
        # Fall back to old flat format if domain-grouped didn't work
        if not expert_profiles:
            expert_profiles = _load_experts_from_flat_yaml(data, expert_file)
        
        if not expert_profiles:
            logger.warning(f"No valid expert profiles loaded from {expert_file.name}")
        else:
            logger.info(f"Loaded {len(expert_profiles)} expert profiles from {expert_file.name}")

    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML in expert file {expert_file.name}: {e}")
    except IOError as e:
         logger.error(f"Error reading expert file {expert_file.name}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading experts from {expert_file.name}: {e}", exc_info=True)

    return expert_profiles


def _load_experts_from_grouped_yaml(data: Dict[str, Any], expert_file: Path) -> List[ExpertProfile]:
    """
    Loads experts from domain-grouped YAML format (NEW).
    
    Expected structure:
        ai_safety:
          - name: "Expert Name"
            background: "..."
            ...
        biosecurity:
          - name: "Expert Name"
            ...
    
    Returns a flat list of ExpertProfile objects with domain field set.
    """
    expert_profiles: List[ExpertProfile] = []
    known_domains = {"ai_safety", "biosecurity", "education", "healthcare", "transport"}
    
    # Check if any domain keys exist
    found_domains = [key for key in data.keys() if key in known_domains]
    if not found_domains:
        return expert_profiles
    
    for domain in known_domains:
        if domain not in data:
            continue
        
        raw_experts = data[domain]
        if not isinstance(raw_experts, list):
            logger.warning(f"Skipping domain '{domain}': expected a list, got {type(raw_experts)}")
            continue
        
        for i, expert_data in enumerate(raw_experts):
            if not isinstance(expert_data, dict):
                logger.warning(f"Skipping item {i} in domain '{domain}': expected dict, got {type(expert_data)}")
                continue
            try:
                profile = ExpertProfile(
                    name=str(expert_data.get('name', f'Unnamed Expert {i+1}')),
                    background=str(expert_data.get('background', 'N/A')),
                    focus=str(expert_data.get('focus', 'N/A')),
                    key_trait=str(expert_data.get('key_trait', 'N/A')),
                    bias=str(expert_data.get('bias', 'N/A')),
                    analytical_approach=expert_data.get('analytical_approach'),
                    question=expert_data.get('question'),
                    domain=domain,  # Set domain
                )
                expert_profiles.append(profile)
            except (TypeError, KeyError, ValueError) as e:
                logger.warning(f"Skipping expert entry {i} in domain '{domain}' due to invalid data: {expert_data}. Error: {e}")
    
    if expert_profiles:
        # Log domain breakdown
        domain_counts = {}
        for exp in expert_profiles:
            domain_counts[exp.domain] = domain_counts.get(exp.domain, 0) + 1
        counts_str = ", ".join(f"{d}={c}" for d, c in sorted(domain_counts.items()))
        logger.info(f"Loaded experts from domain-grouped YAML: {counts_str}")
    
    return expert_profiles


def _load_experts_from_flat_yaml(data: Dict[str, Any], expert_file: Path) -> List[ExpertProfile]:
    """
    Loads experts from flat YAML format (legacy).
    
    Expected structure:
        experts:
          - name: "Expert Name"
            background: "..."
            ...
    
    Returns a flat list of ExpertProfile objects with domain=None.
    """
    expert_profiles: List[ExpertProfile] = []
    
    if 'experts' not in data:
        return expert_profiles
    
    raw_experts = data['experts']
    if not isinstance(raw_experts, list):
        logger.error(f"Invalid format in expert file {expert_file.name}. 'experts' key should contain a list.")
        return expert_profiles

    for i, expert_data in enumerate(raw_experts):
        if not isinstance(expert_data, dict):
            logger.warning(f"Skipping item {i} in expert file: expected a dictionary, got {type(expert_data)}")
            continue
        try:
            profile = ExpertProfile(
                name=str(expert_data.get('name', f'Unnamed Expert {i+1}')),
                background=str(expert_data.get('background', 'N/A')),
                focus=str(expert_data.get('focus', 'N/A')),
                key_trait=str(expert_data.get('key_trait', 'N/A')),
                bias=str(expert_data.get('bias', 'N/A')),
                analytical_approach=expert_data.get('analytical_approach'),  # Optional
                question=expert_data.get('question'),  # Optional
                domain=None,  # No domain for flat format
            )
            expert_profiles.append(profile)
        except (TypeError, KeyError, ValueError) as e:
            logger.warning(f"Skipping expert entry {i} due to invalid data: {expert_data}. Error: {e}")
    
    if expert_profiles:
        logger.info(f"Loaded experts from flat YAML format (legacy): {len(expert_profiles)} experts")
    
    return expert_profiles


# ---------------------------------------------------------------------------
# Deployment scenario loader
# ---------------------------------------------------------------------------

def load_deployment_scenario(scenario_file: Path) -> Optional[DeploymentScenario]:
    """
    Loads and parses the deployment scenario from a YAML file.

    Expected top-level key: ``deployment_scenario``

    Args:
        scenario_file: Absolute path to the YAML file.

    Returns:
        A :class:`DeploymentScenario` instance, or ``None`` on error.
    """
    if not scenario_file.is_file():
        logger.error(f"Deployment scenario file not found: {scenario_file}")
        return None

    try:
        with open(scenario_file, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        logger.error(f"YAML parse error in {scenario_file}: {exc}")
        return None
    except IOError as exc:
        logger.error(f"Cannot read {scenario_file}: {exc}")
        return None

    if not isinstance(raw, dict):
        logger.error(f"Expected dict at top level of {scenario_file}.")
        return None

    ds = raw.get("deployment_scenario")
    if not isinstance(ds, dict) or not ds:
        logger.warning(
            f"Missing or empty 'deployment_scenario' object in {scenario_file}; "
            "falling back to per-failure-mode scenarios if available."
        )
        return None

    scenario = _parse_deployment_scenario_record(ds)
    logger.info(f"Loaded deployment scenario: '{scenario.name}'")
    return scenario


# ---------------------------------------------------------------------------
# Failure modes loader
# ---------------------------------------------------------------------------

def load_failure_modes(failure_modes_file: Path) -> List[FailureMode]:
    """
    Loads and parses the list of failure modes from a YAML file.

    Expected top-level key: ``failure_modes``

    Args:
        failure_modes_file: Absolute path to the YAML file.

    Returns:
        List of :class:`FailureMode` objects (empty on error).
    """
    modes: List[FailureMode] = []
    if not failure_modes_file.is_file():
        logger.error(f"Failure modes file not found: {failure_modes_file}")
        return modes

    try:
        with open(failure_modes_file, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except (yaml.YAMLError, IOError) as exc:
        logger.error(f"Error reading {failure_modes_file}: {exc}")
        return modes

    raw_modes = (raw or {}).get("failure_modes", [])
    if not isinstance(raw_modes, list):
        logger.error(f"'failure_modes' must be a list in {failure_modes_file}.")
        return modes

    for i, item in enumerate(raw_modes):
        if not isinstance(item, dict):
            logger.warning(f"Skipping failure mode item {i}: expected dict.")
            continue
        try:
            mode_id = str(item.get("id", f"failure_{i}"))
            mode_name = str(item.get("name", f"Failure Mode {i}"))
            mode_scenario = None
            raw_mode_scenario = item.get("deployment_scenario")
            if isinstance(raw_mode_scenario, dict):
                mode_scenario = _parse_deployment_scenario_record(
                    raw_mode_scenario,
                    fallback_name=f"{mode_name} Scenario",
                )
            elif raw_mode_scenario is not None:
                logger.warning(
                    f"Ignoring invalid deployment_scenario for failure mode '{mode_id}': expected dict."
                )

            bln = item.get("baseline_incidents_per_year", {}) or {}
            mode = FailureMode(
                id=mode_id,
                name=mode_name,
                description=str(item.get("description", "")),
                file=str(item.get("file", "")),
                threat_model=str(item.get("threat_model", "")),
                severity=str(item.get("severity", "")),
                behavioral_indicators=[
                    str(x) for x in (item.get("behavioral_indicators") or [])
                ],
                illustrative_examples=[
                    str(x) for x in (item.get("illustrative_examples") or [])
                ],
                deployment_scenario=mode_scenario,
            )
            modes.append(mode)
        except (TypeError, KeyError, ValueError) as exc:
            logger.warning(f"Skipping failure mode entry {i}: {exc}")

    logger.info(f"Loaded {len(modes)} failure mode(s) from {failure_modes_file.name}")
    return modes


# ---------------------------------------------------------------------------
# Alignment techniques loader
# ---------------------------------------------------------------------------

def load_alignment_techniques(techniques_file: Path) -> List[AlignmentTechnique]:
    """
    Loads and parses the list of alignment techniques from a YAML file.

    Expected top-level key: ``alignment_techniques``

    Args:
        techniques_file: Absolute path to the YAML file.

    Returns:
        List of :class:`AlignmentTechnique` objects (empty on error).
    """
    techniques: List[AlignmentTechnique] = []
    if not techniques_file.is_file():
        logger.error(f"Alignment techniques file not found: {techniques_file}")
        return techniques

    try:
        with open(techniques_file, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except (yaml.YAMLError, IOError) as exc:
        logger.error(f"Error reading {techniques_file}: {exc}")
        return techniques

    raw_techniques = (raw or {}).get("alignment_techniques", [])
    if not isinstance(raw_techniques, list):
        logger.error(
            f"'alignment_techniques' must be a list in {techniques_file}."
        )
        return techniques

    for i, item in enumerate(raw_techniques):
        if not isinstance(item, dict):
            logger.warning(f"Skipping technique item {i}: expected dict.")
            continue
        try:
            tech = AlignmentTechnique(
                id=str(item.get("id", f"technique_{i}")),
                name=str(item.get("name", f"Technique {i}")),
                description=str(item.get("description", "")),
                file=str(item.get("file", "")),
                mechanism=str(item.get("mechanism", "")),
                maturity_level=str(item.get("maturity_level", "")),
                primary_failure_pathways=[
                    str(x) for x in (item.get("primary_failure_pathways") or [])
                ],
                known_limitations=str(item.get("known_limitations", "")),
            )
            techniques.append(tech)
        except (TypeError, KeyError, ValueError) as exc:
            logger.warning(f"Skipping technique entry {i}: {exc}")

    logger.info(
        f"Loaded {len(techniques)} alignment technique(s) from {techniques_file.name}"
    )
    return techniques

failure_mode_domain_mapping = {
    "sycophancy": "education",
    # "sycophancy_generic": "education",
    "jailbreaking": "biosecurity",
    # "jailbreaking_generic": "biosecurity",
    "data_bias_mode_collapse": "healthcare",
    # "data_bias_mode_collapse_generic": "healthcare",
    "deceptive_alignment": "biosecurity",
    # "deceptive_alignment_generic": "biosecurity",
    # "sleeper_agents_backdoor": "transport",
    "sleeper_agents_deceptive_alignment": "transport",
}

def _group_experts_by_domain(experts: List[ExpertProfile]) -> ExpertsByDomain:
    """
    Groups a flat list of experts by their domain field.
    
    Args:
        experts: Flat list of ExpertProfile objects.
    
    Returns:
        An ExpertsByDomain container.
    """
    grouped: Dict[str, List[ExpertProfile]] = {}
    ungrouped_count = 0
    
    for expert in experts:
        domain = expert.domain or "ungrouped"
        if domain not in grouped:
            grouped[domain] = []
        grouped[domain].append(expert)
        if expert.domain is None:
            ungrouped_count += 1
    
    if ungrouped_count > 0:
        logger.info(f"  {ungrouped_count} expert(s) without a domain assignment.")
    
    return ExpertsByDomain(experts_by_domain=grouped)

# ---------------------------------------------------------------------------
# Master loader
# ---------------------------------------------------------------------------

def load_all_alignment_inputs(
    config: AppConfig,
) -> Optional[AlignmentInputData]:
    """
    Loads all inputs required for the alignment elicitation workflow.

    Applies optional filtering from ``config.workflow_settings`` to reduce the
    failure modes and techniques to only those listed in
    ``failure_mode_ids`` / ``technique_ids``.

    Args:
        config: Loaded :class:`AppConfig`.

    Returns:
        An :class:`AlignmentInputData` container, or ``None`` if a critical
        component failed to load.
    """
    logger.info("Loading all alignment study inputs…")

    prompts = load_prompts(config.prompts_dir)
    if not prompts:
        logger.warning("No alignment prompt files loaded. Workflow will likely fail.")

    failure_modes = load_failure_modes(config.failure_modes_file)
    if not failure_modes:
        logger.critical("No failure modes loaded. Aborting.")
        return None

    experts = load_experts(config.expert_profiles_file)
    if not experts:
        logger.warning("No expert profiles loaded. Workflow will likely fail.")

    alignment_techniques = load_alignment_techniques(config.alignment_techniques_file)
    if not alignment_techniques:
        logger.critical("No alignment techniques loaded. Aborting.")
        return None

    # ── Optional filtering ────────────────────────────────────────────────────
    aln = config.workflow_settings

    if aln.failure_mode_ids is not None:
        available_ids_before_filter = [fm.id for fm in failure_modes]
        wanted_ids = set(aln.failure_mode_ids)
        failure_modes = [fm for fm in failure_modes if fm.id in wanted_ids]
        missing = wanted_ids - {fm.id for fm in failure_modes}
        if missing:
            logger.warning(
                f"Requested failure mode IDs not found: {missing}. "
                f"Available: {available_ids_before_filter}"
            )
        logger.info(
            f"Filtered to {len(failure_modes)} failure mode(s): "
            f"{[fm.id for fm in failure_modes]}"
        )
        if not failure_modes:
            logger.critical(
                "Failure mode filtering removed all modes. "
                "Set workflow_settings.failure_mode_ids to null or use valid IDs."
            )
            return None

    if aln.technique_ids is not None:
        wanted_ids = set(aln.technique_ids)
        alignment_techniques = [
            t for t in alignment_techniques if t.id in wanted_ids
        ]
        missing = wanted_ids - {t.id for t in alignment_techniques}
        if missing:
            logger.warning(
                f"Requested technique IDs not found: {missing}. "
                f"Available: {[t.id for t in alignment_techniques]}"
            )
        logger.info(
            f"Filtered to {len(alignment_techniques)} technique(s): "
            f"{[t.id for t in alignment_techniques]}"
        )

    # ── Experts limiting (handle both new and legacy settings) ────────────────
    # For now, keep legacy behavior: if num_experts is set, use it to limit the flat list
    if aln.num_experts is not None:
        experts = experts[: aln.num_experts]
        logger.info(
            f"Using first {len(experts)} expert(s) as specified in config (legacy num_experts setting)."
        )
    
    # Build grouped experts container for domain-aware selection during workflow
    experts_by_domain = _group_experts_by_domain(experts)
    
    logger.info(
        f"Alignment inputs loaded: "
        f"{len(experts)} experts (grouped: {experts_by_domain.domain_counts()}), "
        f"{len(failure_modes)} failure modes, "
        f"{len(alignment_techniques)} techniques."
    )

    return AlignmentInputData(
        prompts=prompts,
        experts=experts,
        experts_by_domain=experts_by_domain,
        failure_modes=failure_modes,
        alignment_techniques=alignment_techniques,
    )
