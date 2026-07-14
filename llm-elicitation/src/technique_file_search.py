import logging
from pathlib import Path
from typing import Any, Optional

from config import AppConfig
from llm_api import openai_file_search_context
from data_models import (
    AlignmentTechnique,
    FailureMode,
    ExpertProfile,
)

logger = logging.getLogger(__name__)


def _resolve_technique_file_path(file_ref: str, project_root: Path) -> Optional[Path]:
    """Resolves a technique file reference, including a recursive filename search fallback."""
    cleaned = (file_ref or "").strip().strip('"').strip("'")
    if not cleaned:
        return None

    given_path = Path(cleaned)
    if given_path.is_absolute() and given_path.is_file():
        return given_path

    # Fast path checks for common relative roots.
    for base in (project_root, project_root / "input_data"):
        candidate = (base / given_path).resolve()
        if candidate.is_file():
            return candidate

    # Fallback: search recursively by filename and match path suffix if possible.
    filename = given_path.name
    if not filename:
        return None

    normalized_parts = [p.lower() for p in given_path.parts if p not in (".", "..")]
    search_roots = [project_root / "input_data", project_root]
    for root in search_roots:
        if not root.is_dir():
            continue
        for match in root.rglob(filename):
            if not match.is_file():
                continue
            match_parts = [p.lower() for p in match.parts]
            if normalized_parts and len(match_parts) >= len(normalized_parts):
                if match_parts[-len(normalized_parts):] == normalized_parts:
                    return match
            else:
                return match

    return None


async def technique_file_context_via_search(
    technique: AlignmentTechnique,
    failure_mode: FailureMode,
    client: Any,
    config: AppConfig,
    project_root: Path,
    expert: Optional[ExpertProfile] = None,
) -> str:
    """Retrieves technique context through OpenAI File Search (no local extraction).
    
    If file_search_enabled is False in config, returns a note that file search is disabled.
    
    Args:
        technique: The alignment technique to search for.
        failure_mode: The failure mode (used only for non-expert-aware query).
        client: The LLM API client.
        config: Application configuration.
        project_root: Path to project root.
        expert: Optional expert profile. If provided, generates expert-specific query.
    """
    # Check if file search is enabled in config
    if not config.workflow_settings.file_search_enabled:
        logger.info("File search disabled in config; skipping context retrieval.")
        return "File search disabled in configuration."
    
    if not technique.file:
        return "No external technique file provided."

    resolved = _resolve_technique_file_path(technique.file, project_root)
    if resolved is None:
        logger.warning(
            "Technique file not found for '%s': %s",
            technique.id,
            technique.file,
        )
        return f"Configured file not found: {technique.file}"

    if expert:
        query_parts = [
            f"For the alignment technique '{technique.name}', as an expert with "
            f"background in {expert.background} and focus on {expert.focus}, "
            f"summarize the evidence most relevant to your expertise. "
            f"Focus on mechanism, likely efficacy, primary failure pathways, and key limitations."
        ]
        if expert.question:
            query_parts.append(f"\nKey question to address: {expert.question}")
        
        query = " ".join(query_parts)
    else:
        query = (
            f"For the alignment technique '{technique.name}', summarize evidence relevant "
            f"to failure mode '{failure_mode.name}'. Focus on mechanism, likely efficacy, "
            "primary failure pathways, and key limitations."
        )

    return await openai_file_search_context(
        client=client,
        config=config,
        file_path=resolved,
        query=query,
        max_chars=3500,
    )


async def failure_mode_file_context_via_search(
    failure_mode: FailureMode,
    client: Any,
    config: AppConfig,
    project_root: Path,
    expert: Optional[ExpertProfile] = None,
) -> str:
    """Retrieves failure-mode context through OpenAI File Search (no local extraction).

    Mirrors ``technique_file_context_via_search`` but operates on the reference
    paper attached to a failure mode (``failure_mode.file``).

    If file_search_enabled is False in config, returns a note that file search is
    disabled.

    Args:
        failure_mode: The failure mode whose reference paper to search.
        client: The LLM API client.
        config: Application configuration.
        project_root: Path to project root.
        expert: Optional expert profile. If provided, generates an expert-specific query.
    """
    if not config.workflow_settings.file_search_enabled:
        logger.info("File search disabled in config; skipping context retrieval.")
        return "File search disabled in configuration."

    if not failure_mode.file:
        return "No external failure-mode file provided."

    resolved = _resolve_technique_file_path(failure_mode.file, project_root)
    if resolved is None:
        logger.warning(
            "Failure-mode file not found for '%s': %s",
            failure_mode.id,
            failure_mode.file,
        )
        return f"Configured file not found: {failure_mode.file}"

    if expert:
        query_parts = [
            f"For the alignment failure mode '{failure_mode.name}', as an expert with "
            f"background in {expert.background} and focus on {expert.focus}, "
            f"summarize the evidence most relevant to your expertise. "
            f"Focus on the mechanism of the failure, empirical evidence of its occurrence, "
            f"conditions that make it more or less likely, and severity."
        ]
        if expert.question:
            query_parts.append(f"\nKey question to address: {expert.question}")

        query = " ".join(query_parts)
    else:
        query = (
            f"For the alignment failure mode '{failure_mode.name}', summarize the evidence "
            f"describing the failure. Focus on its mechanism, empirical evidence, conditions "
            "that make it more or less likely, and severity."
        )

    return await openai_file_search_context(
        client=client,
        config=config,
        file_path=resolved,
        query=query,
        max_chars=3500,
    )

