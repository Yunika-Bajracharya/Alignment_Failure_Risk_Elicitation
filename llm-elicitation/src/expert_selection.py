
import json
import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from config import AppConfig
from data_models import (
    AlignmentTechnique,
    FailureMode,
    ExpertsByDomain,
    ExpertProfile
)

from data_loader import failure_mode_domain_mapping
from technique_file_search import technique_file_context_via_search


logger = logging.getLogger(__name__)
SemaphoreType = asyncio.Semaphore

async def precompute_technique_contexts_for_experts(
    techniques: List[AlignmentTechnique],
    all_experts: List[ExpertProfile],
    client: Any,
    config: AppConfig,
    project_root: Path,
    semaphore: SemaphoreType,
    output_dir: Optional[Path] = None,
) -> Dict[Tuple[str, str], str]:
    """
    Pre-computes file search results for all (technique, expert) pairs.
    
    Each expert extracts different information from technique papers based on their
    background and focus, leading to more diverse responses.
    
    Results are saved to output_dir/file_search_results.json if output_dir is provided.
    
    Args:
        techniques: List of alignment techniques
        all_experts: List of expert profiles
        client: LLM API client
        config: Application configuration
        project_root: Path to project root
        semaphore: Async semaphore for rate limiting
        output_dir: Optional directory to save results to
    
    Returns:
        Dict mapping (technique_id, expert_name) → file_search_context_string
    """
    if not config.workflow_settings.file_search_enabled:
        logger.info("File search disabled; skipping pre-computation.")
        return {}
    
    logger.info(
        f"\n{'='*60}\n"
        f"PRE-COMPUTING FILE SEARCH CONTEXTS\n"
        f"  Techniques: {len(techniques)}\n"
        f"  Experts: {len(all_experts)}\n"
        f"  Total pairs: {len(techniques) * len(all_experts)}\n"
        f"{'='*60}"
    )
    
    context_cache: Dict[Tuple[str, str], str] = {}
    
    # Create all (technique, expert) tasks
    tasks: List[Tuple[Tuple[str, str], Any]] = []
    for technique in techniques:
        for expert in all_experts:
            cache_key = (technique.id, expert.name)
            # Create a dummy failure_mode for the function signature
            # (expert-aware query doesn't use it)
            dummy_fm = FailureMode(
                id="dummy",
                name="dummy",
                description="",
            )
            
            async def _search_task(t=technique, e=expert, fm=dummy_fm):
                async with semaphore:
                    return await technique_file_context_via_search(
                        technique=t,
                        failure_mode=fm,
                        client=client,
                        config=config,
                        project_root=project_root,
                        expert=e,
                    )
            
            tasks.append((cache_key, _search_task()))
    
    # Execute all tasks concurrently with semaphore control
    logger.info(f"Fetching file search contexts for {len(tasks)} (technique, expert) pairs...")
    results = await asyncio.gather(
        *[task for _, task in tasks],
        return_exceptions=True
    )
    
    # Store results in cache
    for (cache_key, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.warning(
                f"File search failed for {cache_key}: {result}"
            )
            context_cache[cache_key] = f"Error: {str(result)}"
        else:
            context_cache[cache_key] = result
    
    logger.info(f"Pre-computation complete: {len(context_cache)} contexts cached.")
    
    # Save results to JSON file if output_dir provided
    if output_dir is not None:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            results_file = output_dir / "file_search_results.json"
            
            # Convert tuple keys to string keys for JSON serialization
            serializable_cache = {
                f"{tech_id}||{expert_name}": context
                for (tech_id, expert_name), context in context_cache.items()
            }
            
            with open(results_file, "w", encoding="utf-8") as fh:
                json.dump(serializable_cache, fh, indent=2, ensure_ascii=False)
            
            logger.info(f"File search results saved to {results_file}")
        except (IOError, TypeError) as exc:
            logger.error(f"Failed to save file search results: {exc}")
    
    return context_cache


def experts_for_failure_mode(
    failure_mode: FailureMode,
    experts_by_domain: Optional[ExpertsByDomain],
    all_experts_fallback: List[ExpertProfile],
    config: AppConfig,
) -> List[ExpertProfile]:
    """
    Composes the expert panel for a specific failure mode.
    
    Strategy:
    1. Get the domain mapped to this failure mode from failure_mode_domain_mapping.
    2. Collect all AI safety experts (domain == 'ai_safety').
    3. Collect domain-specific experts (domain == mapped_domain).
    4. Combine, deduplicate, and return in deterministic order.
    
    If experts_by_domain is None or domain mapping is missing, falls back to ai_safety_experts only.
    
    Args:
        failure_mode: The failure mode for which to select experts.
        experts_by_domain: Grouped experts by domain (optional).
        all_experts_fallback: Flat list of all experts (fallback).
        config: AppConfig containing expert panel composition settings.
    
    Returns:
        A list of ExpertProfile objects for the failure mode.
    """
    
    aln = config.workflow_settings

    # Collect AI safety experts (shared across all failure modes)
    ai_safety_experts = experts_by_domain.get_experts_by_domain("ai_safety")
    if aln.shared_ai_safety_experts is not None:
        ai_safety_experts = ai_safety_experts[: aln.shared_ai_safety_experts]

    # If no grouped experts available, return fallback
    if experts_by_domain is None:
        logger.debug(
            f"No domain-grouped experts available for failure mode '{failure_mode.id}'; "
            f"using {len(ai_safety_experts)} AI safety experts."
        )
        return ai_safety_experts
    
    # Get the domain for this failure mode
    mapped_domain = failure_mode_domain_mapping.get(failure_mode.id)
    if mapped_domain is None:
        logger.warning(
            f"Failure mode '{failure_mode.id}' has no domain mapping. "
            f"Using {len(ai_safety_experts)} AI safety experts."
        )
        return ai_safety_experts


    # Collect domain-specific experts
    domain_experts = experts_by_domain.get_experts_by_domain(mapped_domain)
    if aln.domain_experts_per_failure_mode is not None:
        domain_experts = domain_experts[: aln.domain_experts_per_failure_mode]
    
    # Combine, deduplicate (by name), and preserve order
    panel: List[ExpertProfile] = []
    seen_names = set()
    
    for expert in ai_safety_experts:
        if expert.name not in seen_names:
            panel.append(expert)
            seen_names.add(expert.name)
    
    for expert in domain_experts:
        if expert.name not in seen_names:
            panel.append(expert)
            seen_names.add(expert.name)
    
    if not panel:
        logger.warning(
            f"No experts selected for failure mode '{failure_mode.id}' (mapped to domain '{mapped_domain}'). "
            f"Falling back to ai safety experts."
        )
        return ai_safety_experts
    
    logger.debug(
        f"Composed panel for failure mode '{failure_mode.id}' (domain '{mapped_domain}'): "
        f"{len(ai_safety_experts)} AI safety + {len(domain_experts)} domain = {len(panel)} total."
    )
    
    return panel
