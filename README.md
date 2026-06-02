# LLM Elicitation for Alignment Failure Risks

This repository contains a pipeline for alignment failure-risk elicitation in [src/main.py](src/main.py). The workflow estimates incident frequency for alignment failure modes under different alignment techniques using a Delphi-style, multi-expert LLM process.

## Alignment Failure-Risk Pipeline

### What it does

The pipeline in [src/](src/) runs in two phases:

1. **Phase 1** — Estimate failure frequency for each (technique × failure-mode) pair.
2. **Phase 2** *(optional)* — Estimate residual risk for stacked techniques (defense-in-depth).

For each cell the pipeline simulates multiple expert personas, runs one or more Delphi rounds, aggregates parsed responses, and stores detailed JSON/CSV outputs. Prompts can optionally be enriched with live web-search context about each alignment technique.

### Quick start

1. Create and activate a virtual environment.

```bash
python -m venv venv
# Windows PowerShell
venv\Scripts\Activate.ps1
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Configure [config.yaml](config.yaml).

```bash
# Optional: start from the provided example
copy config_example.yaml config.yaml
```

4. Set your API key(s) in [config.yaml](config.yaml). **Do not commit real keys.**
5. Run the pipeline.

```bash
python src/main.py -c config.yaml
```

Optional debug logs:

```bash
python src/main.py -c config.yaml -d
```

### Inputs

Configured in [config.yaml](config.yaml):

| File                                                                      | Purpose                                                                       |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| [input_data/expert_profiles.yaml](input_data/expert_profiles.yaml)           | Simulated expert personas                                                     |
| [input_data/deployment_scenario.yaml](input_data/deployment_scenario.yaml)   | Global deployment scenario (can be overridden per failure mode)               |
| [input_data/failure_modes.yaml](input_data/failure_modes.yaml)               | Failure mode definitions; each mode may embed its own `deployment_scenario` |
| [input_data/alignment_techniques.yaml](input_data/alignment_techniques.yaml) | Alignment technique definitions                                               |
| [input_data/prompts/](input_data/prompts/)                                   | Prompt templates for elicitation rounds                                       |

**Deployment scenario resolution order:** a `deployment_scenario` embedded inside a failure mode takes priority over the global `deployment_scenario_file`. If no global scenario is defined, every failure mode must provide its own.

### Outputs

Each run writes to a timestamped directory:

```
output_data/
  runs/<run_id>/
    full_results.json        # Complete results snapshot
    detailed_estimates.csv   # Per-expert, per-round estimates
    plots/                   # Auto-generated visualisations
  run_registry.json          # Index of all runs
```

### Configuration highlights

All settings live in [config.yaml](config.yaml). Key sections:

**API / provider**

```yaml
anthropic_api_key: "..."   # required for Anthropic models
openai_api_key: "..."      # required for OpenAI models
azure_api_key: "..."       # required for Azure OpenAI
azure_endpoint: "..."
azure_api_version: "..."
```

Supported providers: `anthropic`, `openai`, `azure`.

**LLM settings** (`llm_settings`)

| Key                                          | Description                                             |
| -------------------------------------------- | ------------------------------------------------------- |
| `provider`                                 | API provider:`anthropic`, `openai`, or `azure`    |
| `model`                                    | Model identifier, e.g.`claude-sonnet-4-5`, `gpt-4o` |
| `temperature`                              | Sampling temperature (0–2)                             |
| `max_concurrent_calls`                     | Maximum simultaneous API calls                          |
| `rate_limit_calls` / `rate_limit_period` | Rate-limit window (calls per N seconds)                 |
| `thinking.enabled`                         | Enable extended thinking (Anthropic models only)        |
| `thinking.budget_tokens`                   | Token budget for extended thinking                      |

**Web search settings** (`web_search_settings`)

Optionally enriches elicitation prompts with live search results for each technique.

| Key                           | Description                                            |
| ----------------------------- | ------------------------------------------------------ |
| `enabled`                   | Toggle web search enrichment                           |
| `search_provider`           | `duckduckgo` (default) or `bing`                   |
| `max_results_per_technique` | Search results fetched per technique                   |
| `cache_results`             | Cache results to `output_data/web_search_cache.json` |
| `clear_cache`               | Clear the cache at startup                             |
| `include_in_prompts`        | Inject search context into elicitation prompts         |

**Workflow settings** (`workflow_settings`)

| Key                       | Description                                            |
| ------------------------- | ------------------------------------------------------ |
| `failure_mode_ids`      | List of failure-mode IDs to run, or `null` for all   |
| `technique_ids`         | List of technique IDs to evaluate, or `null` for all |
| `num_experts`           | Number of expert personas to simulate (`null` = all) |
| `idea_rounds`         | Total Delphi rounds (1 = initial only)                 |
| `convergence_threshold` | Early-stop when expert std-dev falls below this value  |
| `run_defense_in_depth`  | Enable Phase 2 stacked-technique estimation            |

**Available failure-mode IDs:** `sycophancy`, `sycophancy_generic`, `jailbreaking`, `jailbreaking_generic`, `data_bias_mode_collapse`, `data_bias_mode_collapse_generic`, `deceptive_alignment`, `deceptive_alignment_generic`

**Available technique IDs:** `rlhf`, `constitutional_ai`, `adversarial_finetuning`, `ai_debate`, `ida`, `representation_engineering`, `w2sg`

## Repository Layout

```
src/                        # Pipeline source code
  main.py                   # Entry point
  config.py                 # Configuration loading & validation
  data_loader.py            # Input data loading
  data_models.py            # Dataclass definitions
  llm_api.py                # LLM API client (Anthropic / OpenAI / Azure)
  workflow.py               # Two-phase Delphi elicitation workflow
  parsing.py                # Response parsing utilities
  prompt_helpers.py         # Prompt construction helpers
  websearch.py              # Web search client & cache
  websearch_integration.py  # Prompt enrichment via web search
  plot_fct/                 # Plotting utilities

input_data/                 # Study inputs and prompt templates
output_data/                # Run outputs and registry
```
