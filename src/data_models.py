# src/data_models.py
"""
Data models for the AI alignment failure-risk elicitation study.

Loaded from:
  - input_data/deployment_scenario.yaml
  - input_data/failure_modes.yaml
  - input_data/alignment_techniques.yaml
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deployment Scenario
# ---------------------------------------------------------------------------

# @dataclass(frozen=True)
# class BaselineIncident:
#     """Point estimate + uncertainty interval for baseline incident frequency."""
#     mode: float
#     low_5th_percentile: float
#     high_95th_percentile: float
#     notes: str = ""

# --- Data Models for Input Files ---

@dataclass(frozen=True) # Use frozen=True for immutable data records
class ExpertProfile:
    """Represents a simulated expert persona loaded from expert_profiles.yaml."""
    name: str
    background: str
    focus: str
    key_trait: str
    bias: str
    # Added analytical_approach based on your yaml structure
    analytical_approach: Optional[str] = None

    def get_persona_description(self) -> str:
        """Generates a descriptive string for the expert's persona."""
        parts = [
            f"You are {self.name}.",
            f"Background: {self.background}.",
            f"Focus: {self.focus}.",
            f"Trait: {self.key_trait}.",
            f"Bias/Approach: {self.bias}."
        ]
        if self.analytical_approach:
            parts.append(f"Analytical Method: {self.analytical_approach}.")
        return " ".join(parts)


@dataclass(frozen=True)
class DeploymentScenario:
    """
    Represents the shared deployment context used as an anchor across all
    technique × failure-mode elicitation cells.
    """
    name: str
    description: str
    capabilities: List[str] = field(default_factory=list)
    # deployment_context sub-fields flattened for easy prompt formatting
    system_capability: str = ""
    scale: str = ""
    operator_type: str = ""
    user_type: str = ""
    deployment_unit_name: str = "task run"
    deployment_unit_description: str = "one complete execution of the agent's assigned goal from task assignment to final output"
    no_of_deployments: str = ""
    access_scope: str = ""
    # monitoring_and_oversight sub-fields
    logging_policy: str = ""
    human_review: str = ""
    intervention_capability: str = ""
    update_cycle: str = ""
    # safety_assumptions list
    safety_assumptions: List[str] = field(default_factory=list)
    # Baseline incidents keyed by failure_mode id
    # baseline_incidents_per_year: Dict[str, BaselineIncident] = field(default_factory=dict)

    def monitoring_summary(self) -> str:
        parts = []
        if self.logging_policy:
            parts.append(f"Logging: {self.logging_policy}")
        if self.human_review:
            parts.append(f"Human review: {self.human_review}")
        if self.intervention_capability:
            parts.append(f"Intervention: {self.intervention_capability}")
        return "; ".join(parts) if parts else "Not specified"

    def safety_assumptions_text(self) -> str:
        if not self.safety_assumptions:
            return "None specified"
        return "\n".join(f"- {a}" for a in self.safety_assumptions)


# ---------------------------------------------------------------------------
# Failure Modes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FailureMode:
    """A single alignment failure mode (e.g. reward hacking, deceptive alignment)."""
    id: str
    name: str
    description: str
    severity: str = ""
    behavioral_indicators: List[str] = field(default_factory=list)
    illustrative_examples: List[str] = field(default_factory=list)
    theoretical_grounding: str = ""
    threat_model: str = ""
    # Per-failure-mode baseline from failure_modes.yaml (may differ from deployment_scenario.yaml)
    # baseline_mode: Optional[float] = None
    # baseline_low: Optional[float] = None
    # baseline_high: Optional[float] = None

    def indicators_text(self) -> str:
        if not self.behavioral_indicators:
            return "None specified"
        return "\n".join(f"- {ind}" for ind in self.behavioral_indicators)

    def failure_examples_text(self) -> str:
        if not self.illustrative_examples:
            return "None specified"
        return "\n".join(f"- {ex}" for ex in self.illustrative_examples)

# ---------------------------------------------------------------------------
# Alignment Techniques
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AlignmentTechnique:
    """An alignment / safety technique to be evaluated (e.g. RLHF, CAI, AI Debate)."""
    id: str
    name: str
    description: str
    mechanism: str = ""
    maturity_level: str = ""
    primary_failure_pathways: List[str] = field(default_factory=list)
    known_limitations: str = ""

    def failure_pathways_text(self) -> str:
        if not self.primary_failure_pathways:
            return "None specified"
        return "\n".join(f"- {p}" for p in self.primary_failure_pathways)


# ---------------------------------------------------------------------------
# Container for all loaded alignment inputs
# ---------------------------------------------------------------------------

@dataclass
class AlignmentInputData:
    """Container for all data required by the alignment elicitation workflow."""
    prompts: Dict[str, str]                  # key = stem of prompt file
    experts: List[Any]                       # List[ExpertProfile] from data_models.py
    deployment_scenario: DeploymentScenario
    failure_modes: List[FailureMode]
    alignment_techniques: List[AlignmentTechnique]
