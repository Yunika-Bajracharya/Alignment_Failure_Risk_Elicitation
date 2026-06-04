# src/config.py

import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Basic logger setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Data Structure Definitions ---
@dataclass
class ThinkingSettings:
    """Settings to control Anthropic's extended thinking feature."""
    enabled: bool = False
    budget_tokens: int = 4000

    def __post_init__(self):
        if self.budget_tokens <= 0:
            raise ValueError("ThinkingSettings: 'budget_tokens' must be positive.")

@dataclass
class LLMSettings:
    """Settings related to the LLM and API interaction."""
    provider: str                 # New field to explicitly specify API provider (e.g., "anthropic", "openai", "azure")
    model: str                    # Model identifier (e.g., "claude-3-5-sonnet-20240620")
    temperature: float = 0.8      # LLM sampling temperature
    max_concurrent_calls: int = 5 # Max parallel API requests
    rate_limit_calls: int = 45    # Max calls per rate_limit_period
    rate_limit_period: int = 60   # Time window for rate limit (seconds)
    thinking: ThinkingSettings = field(default_factory=ThinkingSettings)

    def __post_init__(self):
        # Basic validation within the dataclass
        if not self.model:
            raise ValueError("LLMSettings: 'model' cannot be empty.")
        if not self.provider:
            raise ValueError("LLMSettings: 'provider' cannot be empty.")
        if not 0.0 <= self.temperature <= 2.0:
            logger.warning(f"LLMSettings: 'temperature' ({self.temperature}) is outside the typical range [0.0, 2.0].")
        if self.max_concurrent_calls <= 0:
            raise ValueError("LLMSettings: 'max_concurrent_calls' must be positive.")
        if self.rate_limit_calls <= 0:
            raise ValueError("LLMSettings: 'rate_limit_calls' must be positive.")
        if self.rate_limit_period <= 0:
            raise ValueError("LLMSettings: 'rate_limit_period' must be positive.")

@dataclass
class WorkflowSettings:
    """Controls which failure modes / techniques to run and the Delphi parameters."""

    # Expert panel composition - new domain-aware settings
    shared_ai_safety_experts: Optional[int] = None  # None → use all AI safety experts; e.g., 7
    domain_experts_per_failure_mode: Optional[int] = None  # None → use all domain experts; e.g., 3
    # Legacy settings for backward compatibility
    num_experts: Optional[int] = None  # DEPRECATED: use shared_ai_safety_experts + domain_experts_per_failure_mode
    num_domain_experts: Optional[int] = None  # DEPRECATED: replaced by domain_experts_per_failure_mode
    
    idea_rounds: int = 2
    convergence_threshold: float = 0.10         # std-dev threshold (incidents/year)

    # Filter lists (None → run all)
    failure_mode_ids: Optional[List[str]] = None
    technique_ids: Optional[List[str]] = None

    # File Search Settings
    file_search_enabled: bool = True  # Enable/disable OpenAI File Search for technique context retrieval
    technique_ranking_enabled: bool = False  # Whether to run Phase 1B technique ranking for each failure mode.

    # Phase 2 – defense-in-depth
    run_defense_in_depth: bool = True
    # "pairwise"  → all C(n,2) pairs
    # "pairwise_plus_triple" → pairs + one preset triple
    technique_combinations: str = "pairwise"
    preset_triple: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.idea_rounds <= 0:
            raise ValueError("WorkflowSettings: 'idea_rounds' must be positive.")
        if self.convergence_threshold < 0:
            raise ValueError("WorkflowSettings: 'convergence_threshold' cannot be negative.")
        if self.shared_ai_safety_experts is not None and self.shared_ai_safety_experts <= 0:
            raise ValueError("WorkflowSettings: 'shared_ai_safety_experts' must be positive if set.")
        if self.domain_experts_per_failure_mode is not None and self.domain_experts_per_failure_mode <= 0:
            raise ValueError("WorkflowSettings: 'domain_experts_per_failure_mode' must be positive if set.")
        if self.num_experts is not None and self.num_experts <= 0:
            raise ValueError("WorkflowSettings: 'num_experts' must be positive if set.")
        if self.num_domain_experts is not None and self.num_domain_experts <= 0:
            raise ValueError("WorkflowSettings: 'num_domain_experts' must be positive if set.")
        valid_combos = {"pairwise", "pairwise_plus_triple"}
        if self.technique_combinations not in valid_combos:
            raise ValueError(
                f"WorkflowSettings: 'technique_combinations' must be one of {valid_combos}."
            )


# ---------------------------------------------------------------------------
# Root alignment config dataclass
# ---------------------------------------------------------------------------

@dataclass
class AppConfig:
    """Root configuration object for the alignment elicitation pipeline."""

    # ── Input paths ─────────────────────────────────────────────────────────
    prompts_dir: Path
    expert_profiles_file: Path
    failure_modes_file: Path
    alignment_techniques_file: Path

    # ── LLM settings ────────────────────────────────────────────────────────
    llm_settings: LLMSettings

    # ── Study settings ───────────────────────────────────────────────────────
    workflow_settings: WorkflowSettings

    # ── Output ───────────────────────────────────────────────────────────────
    output_dir: Path = Path("output_data")

    # ── API credentials ───────────────────────────────────────────────────────
    api_key_anthropic: Optional[str] = None
    api_key_openai: Optional[str] = None
    api_key_azure: Optional[str] = None
    endpoint_azure: Optional[str] = None
    api_version_azure: Optional[str] = None

    # ── Explicit provider (from config file) ─────────────────────────────────
    _provider_override: Optional[str] = field(default=None, repr=False)

    @property
    def inferred_api_provider(self) -> str:
        """
        Return the API provider.
        Uses the explicit 'provider' key from llm_settings if set; otherwise infers
        from the model name.
        """
        # The LLMSettings dataclass stores the provider field
        if self.llm_settings.provider:
            return self.llm_settings.provider.lower()
        # Fallback: infer from model name
        model_lower = self.llm_settings.model.lower()
        if "claude" in model_lower:
            return "anthropic"
        if "gpt-" in model_lower or model_lower.startswith("o"):
            return "openai"
        raise ValueError(
            f"Cannot infer API provider from model name '{self.llm_settings.model}'. "
            "Set 'provider' explicitly in llm_settings."
        )

    @property
    def runs_dir(self) -> Path:
        return self.output_dir / "runs"

    @property
    def registry_file(self) -> Path:
        return self.output_dir / "run_registry.json"


# ---------------------------------------------------------------------------
# Loader function
# ---------------------------------------------------------------------------

def load_config(config_path: str = "config.yaml") -> AppConfig:
    """
    Loads and validates the alignment study configuration from a YAML file.

    Args:
        config_path: Path (relative or absolute) to the configuration YAML file.

    Returns:
        An AppConfig instance.

    Raises:
        FileNotFoundError, yaml.YAMLError, ValueError, TypeError
    """
    config_file = Path(config_path).resolve()
    if not config_file.is_file():
        raise FileNotFoundError(f"Alignment config file not found: {config_file}")

    logger.info(f"Loading alignment configuration from: {config_file}")

    with open(config_file, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError("Config file must contain a YAML dictionary at the top level.")

    project_root = Path.cwd()

    def _resolve(key: str, default: str, must_exist_as: str = "file") -> Path:
        """Resolve a path from the config; validate existence as 'file' or 'dir'."""
        val = raw.get(key, default)
        if not val:
            raise ValueError(f"Config key '{key}' cannot be empty.")
        resolved = (project_root / Path(str(val))).resolve()
        if must_exist_as == "file" and not resolved.is_file():
            raise ValueError(f"Required file for '{key}' not found: {resolved}")
        if must_exist_as == "dir" and not resolved.is_dir():
            raise ValueError(f"Required directory for '{key}' not found: {resolved}")
        return resolved

    # ── Input paths ──────────────────────────────────────────────────────────
    prompts_dir = _resolve(
        "prompts_dir", "input_data/prompts/alignment", must_exist_as="dir"
    )
    expert_profiles_file = _resolve(
        "expert_profiles_file", "input_data/expert_profiles.yaml"
    )
    failure_modes_file = _resolve(
        "failure_modes_file",
        "input_data/failure_modes.yaml",
    )
    alignment_techniques_file = _resolve(
        "alignment_techniques_file",
        "input_data/alignment_techniques.yaml",
    )

    # ── Output directory ─────────────────────────────────────────────────────
    output_dir_str = raw.get("output_dir", "output_data")
    output_dir = (project_root / Path(str(output_dir_str))).resolve()

    # ── LLM settings ─────────────────────────────────────────────────────────
    llm_raw = raw.get("llm_settings", {})
    if not isinstance(llm_raw, dict):
        raise ValueError("'llm_settings' must be a dictionary.")

    thinking_raw = llm_raw.get("thinking", {})
    if not isinstance(thinking_raw, dict):
        thinking_raw = {}

    thinking_settings = ThinkingSettings(
        enabled=bool(thinking_raw.get("enabled", False)),
        budget_tokens=int(thinking_raw.get("budget_tokens", 4000)),
    )

    llm_settings = LLMSettings(
        provider=str(llm_raw.get("provider", "")).lower(),
        model=str(llm_raw.get("model", "")),
        temperature=float(llm_raw.get("temperature", 1.0)),
        max_concurrent_calls=int(llm_raw.get("max_concurrent_calls", 10)),
        rate_limit_calls=int(llm_raw.get("rate_limit_calls", 45)),
        rate_limit_period=int(llm_raw.get("rate_limit_period", 60)),
        thinking=thinking_settings,
    )

    # ── Alignment settings ────────────────────────────────────────────────────
    aln_raw = raw.get("workflow_settings", {})
    if not isinstance(aln_raw, dict):
        raise ValueError("'workflow_settings' must be a dictionary.")

    preset_triple_raw = aln_raw.get("preset_triple", [])
    if preset_triple_raw is None:
        preset_triple_raw = []

    workflow_settings = WorkflowSettings(
        shared_ai_safety_experts=int(n) if (n := aln_raw.get("shared_ai_safety_experts")) is not None else None,
        domain_experts_per_failure_mode=int(n) if (n := aln_raw.get("domain_experts_per_failure_mode")) is not None else None,
        num_experts=int(n) if (n := aln_raw.get("num_experts")) is not None else None,  # legacy
        num_domain_experts=int(n) if (n := aln_raw.get("num_domain_experts")) is not None else None,  # legacy
        idea_rounds=int(aln_raw.get("idea_rounds", 2)),
        convergence_threshold=float(aln_raw.get("convergence_threshold", 0.10)),
        failure_mode_ids=aln_raw.get("failure_mode_ids"),  # None or list
        technique_ids=aln_raw.get("technique_ids"),        # None or list
        file_search_enabled=bool(aln_raw.get("file_search_enabled", True)),
        technique_ranking_enabled=bool(aln_raw.get("technique_ranking_enabled", False)),

        run_defense_in_depth=bool(aln_raw.get("run_defense_in_depth", True)),
        technique_combinations=str(aln_raw.get("technique_combinations", "pairwise")),
        preset_triple=list(preset_triple_raw),
    )

    # ── API keys ──────────────────────────────────────────────────────────────
    api_key_anthropic = raw.get("anthropic_api_key")
    api_key_openai = raw.get("openai_api_key")
    api_key_azure = raw.get("azure_api_key")
    endpoint_azure = raw.get("azure_endpoint")
    api_version_azure = raw.get("azure_api_version")

    config = AppConfig(
        prompts_dir=prompts_dir,
        expert_profiles_file=expert_profiles_file,
        failure_modes_file=failure_modes_file,
        alignment_techniques_file=alignment_techniques_file,
        llm_settings=llm_settings,
        workflow_settings=workflow_settings,
        output_dir=output_dir,
        api_key_anthropic=str(api_key_anthropic) if api_key_anthropic else None,
        api_key_openai=str(api_key_openai) if api_key_openai else None,
        api_key_azure=str(api_key_azure) if api_key_azure else None,
        endpoint_azure=str(endpoint_azure) if endpoint_azure else None,
        api_version_azure=str(api_version_azure) if api_version_azure else None,
    )

    # ── Validate API key presence ─────────────────────────────────────────────
    provider = config.inferred_api_provider
    if provider == "anthropic" and not config.api_key_anthropic:
        raise ValueError(
            "Anthropic provider selected but 'anthropic_api_key' is missing in config."
        )
    if provider == "openai" and not config.api_key_openai:
        raise ValueError(
            "OpenAI provider selected but 'openai_api_key' is missing in config."
        )
    if provider == "azure" and not config.api_key_azure:
        raise ValueError(
            "Azure provider selected but 'azure_api_key' is missing in config."
        )

    logger.info(
        f"Alignment configuration loaded. Provider: {provider}, "
        f"Model: {llm_settings.model}"
    )
    return config


# ---------------------------------------------------------------------------
# Backward-compatible aliases for shared modules
# ---------------------------------------------------------------------------

# Legacy modules use AppConfig / load_config names. Keep them mapped to
# the alignment config to avoid import-time breakage.
# AppConfig = AppConfig


# def load_config(config_path: str = "config.yaml") -> AppConfig:
#     """Compatibility wrapper that forwards to the alignment config loader."""
#     return load_config(config_path)
