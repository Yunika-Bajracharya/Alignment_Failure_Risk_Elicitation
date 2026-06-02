# LLM Elicitation for Alignment Failure Risks

This repository runs a multi-expert LLM elicitation pipeline to estimate alignment failure risk reduction under different safety techniques.

The codebase currently uses an IDEA-style round structure:

- Round 1: initial expert estimates
- Round 2: expert revision after seeing prior panel context

The pipeline computes:

- Phase 1: single-technique effects by failure mode
- Phase 1B: cross-technique ranking for each failure mode
- Ranking comparison: all-at-once ranking vs implied one-by-one ranking
- Phase 2 (optional): defense-in-depth stacked-technique estimates

## Quick Start

1. Create and activate a virtual environment.

```powershell
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Create a config file (recommended: config.yaml in repo root).
4. Run the pipeline.

```powershell
python src/main.py
```

## What the Pipeline Does

### Phase 1: Single-technique estimation

For each (technique, failure mode) pair:

- Selects a domain-specific expert panel
- Runs IDEA rounds
- Parses structured responses
- Aggregates per-cell final estimates
- Writes per-round CSV rows and JSON snapshots

### Phase 1B: Technique ranking

For each failure mode:

- Asks experts to rank all techniques relative to SFT baseline
- Writes expert-level ranking rows
- Produces aggregated ranking metrics

### Phase 2: Defense in depth (optional)

For each selected technique stack and failure mode:

- Runs IDEA rounds for residual risk
- Aggregates stacked-technique estimates
- Persists per-round rows and JSON snapshots

## Configuration

Configuration is loaded by src/config.py.

### workflow_settings

**Workflow settings** (`workflow_settings`)

| Key                                                         | Description                                            |
| ----------------------------------------------------------- | ------------------------------------------------------ |
| `failure_mode_ids`                                        | List of failure-mode IDs to run, or `null` for all   |
| `technique_ids`                                           | List of technique IDs to evaluate, or `null` for all |
| `shared_ai_safety_experts`                                | Number of expert personas to simulate (`null` = all) |
| `shared_aidomain_experts_per_failure_mode_safety_experts` | Number of expert personas to simulate (`null` = all) |
| `idea_rounds`                                             | Total IDEA rounds (1 = initial only)                   |
| `convergence_threshold`                                   | Early-stop when expert std-dev falls below this value  |
| `run_defense_in_depth`                                    | Enable Phase 2 stacked-technique estimation            |

## Inputs

Configured in [config.yaml](config.yaml)

Core input files:

| File                                                                      | Purpose                                           |
| ------------------------------------------------------------------------- | ------------------------------------------------- |
| [input_data/expert_profiles.yaml](input_data/expert_profiles.yaml)           | Simulated expert personas                         |
| [input_data/failure_modes.yaml](input_data/failure_modes.yaml)               | Failure mode definitions &`deployment_scenario` |
| [input_data/alignment_techniques.yaml](input_data/alignment_techniques.yaml) | Alignment technique definitions                   |
| [input_data/prompts/](input_data/prompts/)                                   | Prompt templates for elicitation rounds           |

Prompt files expected by current workflow include:

- system_context.txt
- initial_failure_estimation.txt
- subsequent_failure_estimation.txt
- defense_in_depth_initial.txt
- defense_in_depth_subsequent.txt
- alignment_technique_ranking.txt

## Outputs

Each run is written under output_data/runs/<run_id>/

Current run artifacts:

```
- full_results.json
- round_1_detailed_estimates.csv
- round_2_detailed_estimates.csv
- technique_rankings.csv
- technique_ranking_comparison.csv
- file_search_results.json (when precompute output is enabled)
- plots/

Global registry:

- output_data/run_registry.json
```

## Project Structure

```text
src/
  main.py                       # CLI entry point and run summary printer
  workflow.py                   # High-level orchestration across phases
  config.py                     # Config dataclasses and YAML loader
  data_models.py                # Core dataclasses
  data_loader.py                # YAML + prompt loading and filtering
  llm_api.py                    # Provider clients, rate limiting, token accounting, file search wrapper
  parsing.py                    # Structured response parsers
  run_io.py                     # Run initialization, CSV/JSON persistence, registry updates
  expert_selection.py           # Domain-aware expert panel selection + context precompute
  prompt_builders.py            # System prompt/scenario resolution helpers
  technique_file_search.py      # Technique file path resolution and OpenAI file search query helper
  idea_engine.py                # Round loop, per-expert phase handlers, aggregation
  plot_fct/
    alignment_result_plots.py   # Phase estimates, disagreement, robust stats, stability plots
    ranking_plots.py            # Ranking summary and ranking comparison plots

input_data/                     # YAML data + prompt templates + optional technique source files
output_data/                    # Run outputs and run registry
```
