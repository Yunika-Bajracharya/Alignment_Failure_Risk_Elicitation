
#### Anchor-based Validation

Before trusting elicited estimates, we check whether a simulated panel reproduces relationships we already have good evidence for — e.g. *"Constitutional Classifiers should outrank RLHF for jailbreaking."* These **relative anchors** are pure-ordinal: they check the *ranking* of cells, not their magnitudes, so they are robust to the 0–100 "% reduction vs SFT" scale.

| File                  | Purpose                                                                                                                                                  |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `anchors_core.yaml` | Focused anchor set for the {RLHF, Constitutional AI, Constitutional Classifiers, Adversarial Fine-Tuning} × {jailbreaking, sycophancy, data bias} grid. |
| `anchors.yaml`      | Broader anchor set (also covers sleeper agents, deceptive alignment, representation engineering).                                                        |
| `anchor_check.py`   | Evaluate**one** run against an anchor file (also importable as a library).                                                                         |
| `anchor_report.py`  | Evaluate**several** runs at once; prints a PASS/FAIL/N-A matrix with per-config pass-rates. Imports `anchor_check.py`.                           |

Two anchor types, both magnitude-free:

- `technique_order` — within a failure mode, the techniques should rank in the given order.
- `failure_order` — for a technique, it should be more vs. less effective on the listed failure modes.

A cell value is the mean of per-expert `estimate` at the cell's final Delphi round. The report also shows *expert agreement* (the fraction of experts who individually satisfy the ordering), and a "common anchors" pass-rate so configs with different N/A sets compare apples-to-apples. Anchors that reference a technique or failure mode absent from a run are reported as **N/A**, never as a failure. Requires `PyYAML`.

**Evaluate a single run** (point it at the `*_detailed_estimates.csv` produced by `llm-elicitation/`):

```bash
python3 anchor_check.py \
  --results path/to/round_1_detailed_estimates.csv path/to/round_2_detailed_estimates.csv \
  --anchors anchors_core.yaml
```

**Evaluate several runs at once** (one sub-folder per run):

```bash
python3 anchor_report.py --runs-dir path/to/results_dir --anchors anchors_core.yaml --csv eval.csv
```

`--runs-dir` discovers every immediate sub-folder containing `*detailed_estimates.csv`, bundles that run's rounds together (using each cell's final round), and labels each config by its folder name (a leading `YYYYMMDD_HHMMSS-` run-id prefix is stripped). Pass `--config "label=fileA,fileB"` (repeatable) instead to specify runs explicitly.