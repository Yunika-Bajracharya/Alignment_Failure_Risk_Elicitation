# Quantifying AI Alignment Failure Risks

*A Structured Expert Elicitation Study*

As AI systems grow more capable, quantifying alignment failure risks becomes critical for risk
management, research prioritization, and policy development. For alignment failures that already occur in present-day systems (e.g., jailbreaking via adversarial prompts), we can empirically test to what extent mature alignment techniques (e.g.Reinforcement Learning from Human Feedback (RLHF)) can mitigate them. However, for failures such as shutdown resistance, which are likely to only occur in more advanced AI systems, such experiments are impossible. Likewise, for alignment techniques that are conceptually promising but not mature enough to be integrated in present-day systems, e.g. AI Debate, the remaining risk is unknown. Mature safety domains from nuclear engineering to cybersecurity have long relied on structured expert elicitation to model uncertain risks. Applying these methods to AI alignment failure modes remains largely uncharted territory.

We present a framework for a structured expert-judgment study that quantifies how likely specific failure modes are to occur and how well different alignment methods mitigate them. Using a scenario-based elicitation framework, we survey AI safety researchers on the expected frequency of specific failure modes under different training-time alignment techniques. All estimates are anchored to a concrete shared deployment scenario to minimize interpretive variance. Participants provide uncertainty intervals, causal rationales, and conditional judgments about an alignment technique's failure mitigation potential. To improve epistemic reliability, we employ the IDEA protocol (Investigate, Discuss, Estimate, Aggregate) and use large language models as pilot simulated experts to stress-test the experimental design before field deployment: Divergent simulated responses reveal ambiguities in failure definitions, causal assumptions, and scenario framing. Addressing these issues prior to human elicitation improves the reliability and epistemic interpretability of the resulting expert judgments.

#### Repository Layout

| Directory | Description |
|-----------|-------------|
| [elicitation-app/](https://github.com/Yunika-Bajracharya/Alignment_Failure_Risk_Elicitation/tree/main/elicitation-app) | A React survey app for collecting structured expert assessments. |
| [llm-elicitation/](https://github.com/Yunika-Bajracharya/Alignment_Failure_Risk_Elicitation/tree/main/llm-elicitation) | A Python pipeline for running multi-expert LLM elicitation over alignment failure risks. |


#### License

See [LICENSE](LICENSE) for the repository license.
