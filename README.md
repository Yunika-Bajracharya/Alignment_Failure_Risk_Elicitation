# Quantifying AI Alignment Failure Risks

*A Structured Expert Elicitation Study*

How much do safety techniques mitigate different failure modes?

🔗 Elicitation app: https://alignment-failure-risk-elicitation.vercel.app/

---

## Abstract

As AI systems grow more capable, quantifying alignment failure risks becomes critical for risk management, research prioritization, and policy development. For alignment failures that already occur in present-day systems (e.g., jailbreaking via adversarial prompts), we can empirically test to what extent mature alignment techniques (e.g., Reinforcement Learning from Human Feedback) can mitigate them. However, for failures such as shutdown resistance, which are likely to only occur in more advanced AI systems, such experiments are impossible. Likewise, for alignment techniques that are conceptually promising but not mature enough to be integrated in present-day systems, e.g. AI Debate, the remaining risk is unknown. Mature safety domains from nuclear engineering to cybersecurity have long relied on structured expert elicitation to model uncertain risks. Applying these methods to AI alignment failure modes remains largely uncharted territory.

We present a framework for a structured expert-judgment study that quantifies how likely specific failure modes are to occur and how well different alignment methods mitigate them. Using a scenario-based elicitation framework, we survey AI safety researchers on the expected frequency of specific failure modes under different training-time alignment techniques. All estimates are anchored to a concrete shared deployment scenario to minimize interpretive variance. Participants provide uncertainty intervals, causal rationales, and conditional judgments about an alignment technique's failure mitigation potential. To improve epistemic reliability, we employ the IDEA protocol (Investigate, Discuss, Estimate, Aggregate) and use large language models as pilot simulated experts to stress-test the experimental design before field deployment: divergent simulated responses reveal ambiguities in failure definitions, causal assumptions, and scenario framing. Addressing these issues prior to human elicitation improves the reliability and epistemic interpretability of the resulting expert judgments.

---

## Motivation

AI capability is rising faster than our ability to measure risk. Each capability leap brings new failure modes. We have a growing toolbox of alignment techniques, but there is no standard way to quantify how much a given technique reduces a given failure mode.

|                                             | Failure exists today                                                               | Failure likely in more advanced AI                                                                |
| ------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Established technique<br />(deployed today) | Can be tested empirically<br />*e.g. Jailbreaking × Constitutional Classifiers* | Hard to test; failure can't be fully reproduced<br />*e.g. Deceptive Alignment × RLHF*        |
| Emerging technique<br />(not mature enough) | Hard to test empirically<br />*e.g. Sycophancy × AI Debate*                     | Doubly unknown; emerging method × speculative failure<br />t*e.g. Sleeper Agents × AI Debate* |

Only the top-left cell is reachable by experiment. For failures like deceptive alignment or shutdown resistance, which show early signs in current systems but are expected to matter most in more advanced AI, we cannot reproduce the failure well enough to run a clean experiment. Likewise, techniques such as AI Debate or IDA are conceptually promising but not deployed widely enough to yield empirical data.

Structured expert elicitation is standard practice in mature, high-stakes fields for situation like this. But applying these methods to AI alignment failure risks remains largely uncharted territory. That is the gap this project addresses.

Quantified estimates help us in research prioritisation, identifying gaps (which failure modes have no adequate defense), risk management (what residual risk remains after a technique is applied), policy development, and to have clearer overall view of where the safety techniques stand.

---

## The Idea

Prior work by [Dung &amp; Mai](https://arxiv.org/abs/2510.11235), *AI Alignment Strategies from a Risk Perspective: Independent Safety Mechanisms or Shared Failures?*, produced a qualitative map of alignment methods against risk dimensions. It is a valuable map, but it rests on the qualitative judgement of two researchers. Our idea is to broaden that map into a structured elicitation across a panel of experts, with:

- quantified estimates (% failure reduction relative to an SFT baseline),
- explicit uncertainty (lower/upper intervals plus a confidence score),
- recorded rationales, and
- a structured discussion round in which experts see each other's reasoning and revise.

Before running this with human experts, we first run the entire protocol with LLMs role-playing as expert personas, for two reasons: (1) to stress-test the experimental design and surface ambiguities in our failure-mode and technique descriptions and (2) to test whether LLM panels can serve as a cheaper proxy for expert elicitation.

## Repository Layout

| Directory                                                       | Description                                                                                                                                                                                    |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`elicitation-app/`](elicitation-app/)                         | survey app for collecting structured expert assessments from human experts. Deployed at https://alignment-failure-risk-elicitation.vercel.app/                                                 |
| [`llm-elicitation/`](llm-elicitation/)                         | Python pipeline that runs the multi-expert LLM elicitation over alignment failure risks (IDEA rounds, file search, aggregation, plots).                                                        |
| [`expert_elicitation_workshop/`](expert_elicitation_workshop/) | Scripts for running the elicitation as a live workshop: fetching submitted results, dividing participants into role-diverse discussion groups, and generating round-1 / round-2 summary decks. |

### Pipeline

```
1 · Load inputs          scenario, failure modes, techniques, prompts
2 · Compose panel        7 AI-safety + 3 domain experts per failure mode
3 · Retrieve evidence    each expert runs file search over the technique's paper
4 · Round 1 (Estimate)   independent three-point estimate + confidence + rationale
5 · Aggregate            PERT per expert → mean across experts
6 · Round 2 (Discuss)    panel summary + all rationales shown to every expert
7 · Revise               revise in light of peers' arguments, or defend
8 · Aggregate            final per-cell estimate
```

Additional phases the pipeline supports:

- Phase 1B: technique ranking: experts rank *all* techniques for a failure mode at once, which is then compared against the ranking implied by the one-by-one estimates.
- Phase 2: defense in depth: risk estimation for stacked technique combinations.

---

## Validation: Anchor Checks

Before trusting the elicited numbers, we check whether the panel reproduces relationships we already have evidence for. Anchors are ordinal, not magnitude-based.

| Anchor type         | Statement                                                                        | Example                                                                                                                   |
| ------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `technique_order` | Within a failure mode, techniques should rank in a given order.                  | For jailbreaking: Constitutional Classifiers > RLHF<br />(source: ASR 86 % → <5 % with classifiers)                      |
| `failure_order`   | For a technique, it should be more vs. less effective between two failure modes. | Adversarial fine-tuning: backdoors < jailbreaking<br />(source: reduces red-team behaviour but leaves the trigger intact) |

See [`llm-elicitation/src/anchor/README.md`](llm-elicitation/src/anchor/README.md)

---

## Next Steps

The success of defense in depth depends on how uncorrelated the failure modes are across techniques. If every technique failed in exactly the same circumstances, stacking them would add no protection at all. Our next steps:

1. Improving LLM elicitation pipeline, experimenting across different LLMs.
2. Measure correlated failures: test defense in depth directly by eliciting *joint* failure across technique stacks, and identify which combinations work best.
3. Human elicitation: run the elicitation with a real expert panel across disciplines.
4. LLM vs. human: compare simulated and human estimates: where do LLM panels agree, and where do they mislead?

> This project is a work in progress. Questions and feedback are very welcome.

---
