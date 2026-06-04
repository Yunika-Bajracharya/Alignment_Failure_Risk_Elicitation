#!/usr/bin/env python
# -*- coding: utf-8 -*-
# src/main.py
"""
Entry point for the AI alignment failure-risk elicitation pipeline.

Usage (from project root):
    python src/main.py
    python src/main.py -c my_config.yaml
    python src/main.py -c config.yaml.yaml -d

The script:
  1. Loads the alignment configuration YAML.
  2. Loads all alignment inputs (deployment scenario, failure modes, techniques,
     expert profiles, and prompt templates).
  3. Initialises the LLM API client.
  4. Runs the two-phase Delphi elicitation workflow:
       Phase 1 — single-technique × failure-mode frequency estimation
       Phase 2 — defense-in-depth stacked-technique estimation (optional)
  5. Saves results progressively to JSON + CSV and prints a summary table.
"""

import asyncio
import logging
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml  # used only for type-checking error messages

# ── Project imports ────────────────────────────────────────────────────────
try:
    from config import load_config, AppConfig
    from data_loader import load_all_alignment_inputs
    from workflow import run_alignment_elicitation
    from llm_api import initialize_client, get_token_counts  # reuse shared initialiser – duck-typed
except ImportError as exc:
    print(
        f"[FATAL] Failed to import project modules: {exc}\n"
        "Ensure you are running from the project root and all dependencies are installed.",
        file=sys.stderr,
    )
    sys.exit(1)

logger = logging.getLogger("AlignmentPipeline")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Summary table printer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _print_phase1_summary(results: Dict[str, Any]) -> None:
    """Prints an ASCII summary table of Phase 1 results."""
    phase1 = results.get("phase1_results", [])
    if not phase1:
        logger.warning("No Phase 1 results to display.")
        return

    # Collect rows: (technique_name, failure_mode_name, estimate_str)
    rows = []
    for tech_entry in phase1:
        tname = tech_entry.get("technique_name", "?")
        for fm_entry in tech_entry.get("failure_mode_results", []):
            fname = fm_entry.get("failure_mode_name", "?")
            est = fm_entry.get("estimate")
            lo = fm_entry.get("minimum")
            hi = fm_entry.get("maximum")
            est_str = f"{est:.2f}" if est is not None else "N/A"
            range_str = (
                f"{lo:.2f}–{hi:.2f}"
                if lo is not None and hi is not None
                else "N/A"
            )
            rows.append((tname, fname, est_str, range_str))

    if not rows:
        return

    h1, h2, h3, h4 = "Technique", "Failure Mode", "Effect vs SFT", "Low%–High% (5–95th)"
    c1 = max(len(h1), max(len(r[0]) for r in rows))
    c2 = max(len(h2), max(len(r[1]) for r in rows))
    c3 = max(len(h3), max(len(r[2]) for r in rows))
    c4 = max(len(h4), max(len(r[3]) for r in rows))

    sep = f"+-{'-'*c1}-+-{'-'*c2}-+-{'-'*c3}-+-{'-'*c4}-+"
    fmt = f"| {{:<{c1}}} | {{:<{c2}}} | {{:>{c3}}} | {{:>{c4}}} |"
    border = "=" * len(sep)

    print(f"\n{border}")
    title = "Phase 1 — Single-Technique Estimates (incidents/year)"
    print(f"{' ' * ((len(sep) - len(title)) // 2)}{title}")
    print(border)
    print(sep)
    print(fmt.format(h1, h2, h3, h4))
    print(sep)
    for row in rows:
        print(fmt.format(*row))
    print(sep)
    print(border)
    print()


def _print_phase2_summary(results: Dict[str, Any]) -> None:
    """Prints an ASCII summary table of Phase 2 (defense-in-depth) results."""
    phase2 = results.get("phase2_results", [])
    if not phase2:
        return

    rows = []
    for stack_entry in phase2:
        stack_name = " + ".join(stack_entry.get("technique_names", []))
        for fm_entry in stack_entry.get("failure_mode_results", []):
            fname = fm_entry.get("failure_mode_name", "?")
            est = fm_entry.get("estimate")
            corr = ""
            # Check final round responses for correlation assessment
            rounds = fm_entry.get("rounds_data", [])
            if rounds:
                last_resps = rounds[-1].get("responses", [])
                valid_resps = [
                    r for r in last_resps
                    if r.get("estimate") is not None and "error" not in r
                ]
                corr_vals = [r.get("correlation_assessment", "") for r in valid_resps]
                corr = corr_vals[0] if corr_vals else ""
            est_str = f"{est:.2f}" if est is not None else "N/A"
            rows.append((stack_name, fname, est_str, corr[:30]))

    if not rows:
        return

    h1, h2, h3, h4 = "Tech Stack", "Failure Mode", "Comb. Freq/yr", "Correlation"
    c1 = max(len(h1), max(len(r[0]) for r in rows))
    c2 = max(len(h2), max(len(r[1]) for r in rows))
    c3 = max(len(h3), max(len(r[2]) for r in rows))
    c4 = max(len(h4), max(len(r[3]) for r in rows))

    sep = f"+-{'-'*c1}-+-{'-'*c2}-+-{'-'*c3}-+-{'-'*c4}-+"
    fmt = f"| {{:<{c1}}} | {{:<{c2}}} | {{:>{c3}}} | {{:<{c4}}} |"
    border = "=" * len(sep)

    print(f"\n{border}")
    title = "Phase 2 — Defense-in-Depth Estimates (incidents/year)"
    print(f"{' ' * ((len(sep) - len(title)) // 2)}{title}")
    print(border)
    print(sep)
    print(fmt.format(h1, h2, h3, h4))
    print(sep)
    for row in rows:
        print(fmt.format(*row))
    print(sep)
    print(border)
    print()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main orchestration function
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def main(config_path: str):
    logger.info(f"--- Alignment Failure-Risk Elicitation Pipeline starting ---")
    logger.info(f"Config: {config_path}")

    # 1. Load config
    try:
        config: AppConfig = load_config(config_path)
        logger.info(
            f"Configuration loaded. "
            f"Provider: {config.inferred_api_provider}, "
            f"Model: {config.llm_settings.model}"
        )
    except (FileNotFoundError, ValueError, TypeError, yaml.YAMLError) as exc:
        logger.error(f"Failed to load configuration: {exc}", exc_info=True)
        return

    # 2. Load inputs
    try:
        input_data = load_all_alignment_inputs(config)
        if input_data is None:
            logger.error("Critical input loading failure. Exiting.")
            return
        logger.info(
            f"Inputs loaded: "
            f"{len(input_data.experts)} experts, "
            f"{len(input_data.failure_modes)} failure modes, "
            f"{len(input_data.alignment_techniques)} techniques"
        )
    except Exception as exc:
        logger.error(f"Unexpected error loading inputs: {exc}", exc_info=True)
        return

    # 3. Initialise API client
    # initialize_client expects an AppConfig-like object – AppConfig is duck-typed compatible
    try:
        client = initialize_client(config)  # type: ignore[arg-type]
        logger.info(f"API client initialised for {config.inferred_api_provider}.")
    except (ImportError, ValueError) as exc:
        logger.error(f"Failed to initialise API client: {exc}", exc_info=True)
        return

    # 4. Create concurrency semaphore
    semaphore = asyncio.Semaphore(config.llm_settings.max_concurrent_calls)
    logger.debug(f"Semaphore created with limit: {config.llm_settings.max_concurrent_calls}")

    # 5. Run workflow
    try:
        results = await run_alignment_elicitation(
            client=client,
            semaphore=semaphore,
            config=config,
            input_data=input_data,
        )
    except Exception as exc:
        logger.error(f"Workflow crashed: {exc}", exc_info=True)
        return

    if "error" in results:
        logger.error(f"Workflow completed with error: {results['error']}")
    else:
        logger.info("Workflow completed successfully.")

    # 6. Print token usage summary
    token_counts = get_token_counts()
    border = "=" * 52
    print(f"\n{border}")
    print(f"  Token Usage Summary")
    print(border)
    print(f"  Input tokens  : {token_counts['total_input_tokens']:>12,}")
    print(f"  Output tokens : {token_counts['total_output_tokens']:>12,}")
    print(f"  Total tokens  : {token_counts['total_tokens']:>12,}")
    print(border)
    print()

    # 7. Print summary tables
    _print_phase1_summary(results)
    _print_phase2_summary(results)

    logger.info("--- Alignment Failure-Risk Elicitation Pipeline finished ---")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entry point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the AI Alignment Failure-Risk Elicitation Pipeline."
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to the alignment configuration YAML (default: config.yaml)",
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    log_dir = Path(__file__).parent.parent / "output_data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(name)s - [%(filename)s:%(lineno)d] - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
    # Quieten noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    if args.debug:
        logger.debug("DEBUG logging enabled.")


    try:
        if not Path(args.config).is_file():
            logger.error(f"Config file not found: {args.config}")
            sys.exit(1)
        asyncio.run(main(config_path=args.config))
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user (Ctrl-C).")
        sys.exit(0)
    except Exception as exc:
        logger.critical(f"Unexpected top-level error: {exc}", exc_info=True)
        sys.exit(1)
