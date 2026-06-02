import logging
from typing import Dict, Optional

from data_models import (
    DeploymentScenario,
    FailureMode,
    ExpertProfile
)

logger = logging.getLogger(__name__)

def build_system_prompt(
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


def scenario_for_failure_mode(
    failure_mode: FailureMode,
    default_scenario: Optional[DeploymentScenario],
) -> DeploymentScenario:
    """Returns the scenario to use for a failure mode (mode-specific first)."""
    if failure_mode.deployment_scenario is not None:
        return failure_mode.deployment_scenario
    if default_scenario is not None:
        return default_scenario
    raise ValueError(
        f"No deployment scenario available for failure mode '{failure_mode.id}'."
    )
