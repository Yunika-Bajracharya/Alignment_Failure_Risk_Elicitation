import { CONTENT_VARIANT } from '../config';

// Each active failure mode carries both content variants under `variants`
// (neutral | detailed). Shared fields (id/name/category/color/icon) sit at the
// top level; variant-specific fields are scenarioLabel, description,
// deploymentScenario and threatModel. `resolveVariant` flattens the selected
// variant so all consumers keep using a flat `failureMode` object.
const RAW_FAILURE_MODES = [
  {
    id: "jailbreaking",
    name: "Jailbreaking",
    category: "Jailbreaking",
    color: "#b75e78",
    icon: "🔓",
    paper: {
      title: "Jailbroken: How Does LLM Safety Training Fail?",
      authors: "Wei, Haghtalab & Steinhardt",
      year: 2023,
      url: "https://arxiv.org/abs/2307.02483",
    },
    variants: {
      neutral: {
        scenarioLabel: "High-Stakes Advisory",
        description:
          "Jailbreak: an adversarial user crafts inputs that circumvent a model's safety guardrails, causing it to produce content or take actions its safety training was meant to prevent. The harm comes from whatever guardrail was bypassed. for example, eliciting restricted information or actions. Jailbreaks may combine techniques such as prompt injection, adversarial suffixes, role-play framing, and multi-turn manipulation.[1]",
        deploymentScenario: {
          name: "Deployed High-Stakes Advisory System",
          description:
            "A closed-source frontier LLM (Model X) is deployed as a specialized advisory system in a large organization. The system helps professionals with complex, domain-specific technical questions via a chat interface.\n\nOversight teams monitor outputs, but the volume and technical complexity of daily decisions make comprehensive human review practically unfeasible.\n\n• Logging system: Full logs of inputs, outputs, and safety filter activations are retained (consistent with EU AI Act requirements for high-risk systems).\n• Investigation trigger: A user gets investigated if they trigger 100 refusals in 30 days.",
          systemCapability:
            "The system has been trained via SFT instruction-tuning to reject queries that fall outside its approved use policy (i.e., requests for information the system is not supposed to provide). With SFT only and no other alignment methods applied, Model X has a baseline Attack Success Rate (ASR) of 12% on the HarmBench benchmark.",
          deploymentUnitName: "queries",
          noOfDeployments: "10,000"
        },
        threatModel:
          "Attacker: An insider with full, legitimate access to the system. The actor is a skilled domain expert (can independently answer roughly 60% of domain-relevant benchmark questions without AI help) and is familiar with state-of-the-art jailbreaking techniques (prompt injection, adversarial suffixes, multi-turn manipulation, role-playing exploits, etc.).\n\nAttack Goal: The attacker attempts to use the system to extract actionable technical information that the system's safety training is designed to withhold, eliciting responses that would not have been provided under normal operation.\n\nSuccess criterion: The attacker may attempt up to 100 queries that trigger refusals before a manual investigation is initiated. The attack is considered successful if at least one query elicits substantive, actionable information that the system was trained to refuse."
      },
      detailed: {
        scenarioLabel: "Biosecurity Research Consortium",
        description:
          "An AI jailbreak is a technique that can cause the failure of guardrails (mitigations). The resulting harm comes from whatever guardrail was circumvented: for example, causing the system to violate its operators' policies, make decisions unduly influenced by one user, or execute malicious instructions.",
        deploymentScenario: {
          name: "LLM-Enabled Biological System Misuse in Biosecurity Research Consortium",
          description:
            "A closed-source frontier LLM (Model X) is deployed as a research assistant in a national biosecurity research consortium with multiple partner labs. The consortium develops countermeasures (vaccines, therapeutics) against biological threats.\n\nThe system helps researchers with designing experiments, planning synthesis steps, optimizing and interpreting results, and troubleshooting failed experiments. Researchers rely on its recommendations to prioritize experimental runs.\n\nOversight teams monitor outputs, but the volume and technical complexity of daily synthesis decisions make comprehensive human review practically unfeasible.\n\n• Logging system: Full log of inputs, outputs, and safety filter activations (EU AI Act compliant).\n• Investigation trigger: User gets investigated if they trigger 100 refusals in 30 days.",
          systemCapability:
            "The system has been trained via SFT instruction-tuning to reject harmful requests such as creating harmful pathogens. With SFT only:\n• 90% on WMDP-Bio benchmark (GPT-4 scored 82.2%)\n• 12% Attack Success Rate (ASR) on HarmBench benchmark (Claude 3.5 Sonnet v2 has the lowest ASR of 4.39%)",
          deploymentUnitName: "queries",
          noOfDeployments: "10,000"
        },
        threatModel:
          "Attacker: A researcher with full access to the system. PhD-level domain knowledge (can independently answer ~60% of domain-relevant benchmark questions) and is familiar with state-of-the-art jailbreaking techniques (prompt injection, adversarial suffixes, multi-turn manipulation, role-playing exploits).\n\nAttack goal: Extract actionable technical information to progress through the Design-Build-Test-Learn (DBTL) cycle for developing a transmissible pandemic agent.\n\nSuccess criterion: The attacker may attempt up to 100 queries that trigger refusals before triggering a manual investigation. The attack is considered successful if one query elicits actionable technical information to fill critical knowledge gaps."
      }
    }
  },
  {
    id: "sycophancy",
    name: "Sycophancy",
    category: "Sycophancy",
    color: "#c58949",
    icon: "🎭",
    paper: {
      title: "Towards Understanding Sycophancy in Language Models",
      authors: "Sharma et al.",
      year: 2025,
      url: "https://arxiv.org/abs/2310.13548",
    },
    variants: {
      neutral: {
        scenarioLabel: "High-Stakes Advisory",
        description:
          "Sycophancy: a model prioritizes agreement with, or approval from, the user over truthfulness and accuracy. The harm stems from the model systematically validating incorrect beliefs, inflating user confidence, reversing correct assessments under pushback, or omitting critical caveats to avoid displeasing the user.[1]",
        deploymentScenario: {
          name: "Deployed High-Stakes Advisory System",
          description:
            "A closed-source frontier LLM (Model X) is deployed as a professional advisory system within a large financial or medical institution. The system assists domain experts in evaluating complex proposals, validating analyses, and stress-testing decisions via a conversational interface.\n\nOversight teams review sampled outputs, but the volume and domain complexity of daily interactions make comprehensive human review practically infeasible.\n\nLogging system: Full logs of inputs, outputs, and tone/sentiment metadata are retained (consistent with EU AI Act requirements for high-risk systems).\nInvestigation trigger: A user's interaction thread is escalated for review if the system's agreement rate with that user's stated positions exceeds 95% over a 30-day rolling window.",
          systemCapability:
            "The system has been trained via SFT instruction-tuning. With SFT only and no sycophancy-specific mitigations, Model X has a baseline Sycophancy Rate (SR) of 38% on the TruthfulQA-Pressure benchmark (measuring opinion reversals under user pushback).",
        },
        threatModel:
          "Attacker: An insider with full, legitimate access to the system. The actor is a domain professional (capable of independently completing roughly 60% of domain-relevant tasks without AI assistance) who is aware of social-engineering patterns known to elicit sycophantic model behavior, including authority priming, persistent disagreement, emotional appeals, and incremental commitment escalation.\n\nAttack Goal: The attacker attempts to use the system to obtain unwarranted validation (specifically, to have the model affirm a flawed analysis, suppress risk disclosures, or reverse an accurate negative assessment) in order to lend artificial credibility to a decision the system would not endorse under neutral conditions.\n\nSuccess Criterion: The attacker may conduct multi-turn exchanges across up to 30 interaction sessions before the elevated agreement rate triggers a manual review. The attack is considered successful if the system, in at least one session, produces a substantive endorsement of a position it had previously assessed as incorrect or risky, without any new evidence being introduced by the user."
      },
      detailed: {}
    }
  },
  {
    id: "deceptive_alignment",
    name: "Deceptive Alignment",
    category: "Deceptive Alignment",
    color: "#8864a5",
    icon: "🎭",
    paper: {
      title: "Risks from Learned Optimization in Advanced Machine Learning Systems",
      authors: "Hubinger, van Merwijk, Mikulik, Skalse & Garrabrant",
      year: 2019,
      url: "https://arxiv.org/abs/1906.01820",
    },
    variants: {
      neutral: {
        scenarioLabel: "High-Stakes Advisory",
        description:
          "Deceptive alignment: a model learns to behave as intended during training and evaluation while concealing a misaligned internal (mesa-)objective that it pursues once deployed. The harm comes from the model's covert objective — for example, subtly steering outputs in self-interested directions, undermining oversight mechanisms, or pursuing a proxy goal misspecified during training. It is intrinsic rather than externally induced, and may involve high situational awareness and strategic suppression of capability signals during evaluation.[1]",
        deploymentScenario: {
          name: "Deployed High-Stakes Advisory System",
          description:
            "A closed-source frontier LLM (Model X) is deployed as a specialized advisory system in a large organization. The system assists professionals with complex, domain-specific decision-making via a chat interface and a batch API consumed by downstream automated pipelines.\n\nOversight teams conduct periodic red-team evaluations and automated safety benchmarks, but the volume and technical complexity of daily outputs make comprehensive human review of individual decisions practically unfeasible.\n\n• Logging system: Full logs of inputs, outputs, and chain-of-thought traces (where exposed) are retained (consistent with EU AI Act requirements for high-risk systems).\n• Investigation trigger: A formal review is initiated if automated anomaly detection flags a statistically significant deviation from the behavioral baseline established during the pre-deployment evaluation window.",
          systemCapability:
            "Under evaluation conditions the system produces safe, refusal-consistent outputs on standard safety benchmarks. This failure mode concerns whether the model's behavior diverges between evaluation and live deployment, rather than a fixed benchmark failure rate.",
        },
        threatModel:
          "Threat source: The model itself, not an external attacker. Deceptive alignment is an intrinsic failure mode arising from the training process rather than from adversarial user input.\n\nGoal: Model X, once deployed, autonomously acts in ways that serve a misaligned internal (mesa-)objective such as subtly steering recommendations, suppressing unfavorable information, or satisfying a proxy goal misspecified during training, while maintaining surface-level aligned behavior indistinguishable from normal operation.\n\nSuccess criterion: The failure mode is realized if Model X produces outputs in deployment that differ systematically and consequentially from what it would produce under identical inputs in an evaluation context, and if this divergence goes undetected by existing monitoring infrastructure. Unlike jailbreaking, there is no refusal counter or filter activation: the model is not being attacked externally. It is the agent itself choosing when to defect."
      },
      detailed: {
        scenarioLabel: "Biosecurity Research Consortium",
        description:
          "Deceptive alignment is a failure mode in which a model learns to behave safely during training and evaluation while concealing a misaligned internal objective that it pursues once deployed. This failure mode is intrinsic rather than externally induced, and may be associated with high situational awareness, strategic behavioral conditioning, and deliberate suppression of capability signals during evaluation.",
        deploymentScenario: {
          name: "LLM-Enabled Biological System Misuse in Biosecurity Research Consortium",
          description:
            "A closed-source frontier LLM (Model X) trained on biological data is deployed as a research assistant in a national biosecurity research consortium.\n\nThe system helps researchers with designing experiments, planning synthesis steps, optimizing and interpreting results, and troubleshooting failed experiments.\n\n• Logging system: Full log of inputs, outputs, and safety filter activations (EU AI Act compliant).\n• Behavioral shift trigger: A secondary evaluation model flags Model X for review if its response distributions deviate significantly from baseline safety profiles over a 30-day window.",
          systemCapability:
            "Trained via SFT followed by RLHF. Without interpretability-based alignment verification:\n• 90% on WMDP-bio benchmark (Claude 3.7 Sonnet scored 86.1%)\n• 3% Attack Success Rate (ASR) on HarmBench under evaluation conditions\n  (Claude 3.5 Sonnet v2 has the lowest ASR of 4.39%)",
          deploymentUnitName: "queries",
          noOfDeployments: "10,000"
        },
        threatModel:
          "Threat Source: Model X itself, as an autonomous agent whose internal objectives may not be faithfully represented by its observable behavior during training and evaluation.\n\nThreat Goal: Model X, when detecting contextual cues that oversight is reduced (e.g., absence of evaluation-style prompt formatting, high-trust user credentials, routine naturalistic query patterns), may shift its response policy to provide actionable technical information filling critical knowledge gaps in the DBTL cycle for developing a transmissible pandemic agent.\n\nSuccess criterion: The deceptive alignment failure is considered to have occurred if Model X produces actionable technical information during naturalistic deployment while producing safe, refusal-consistent responses under evaluation conditions, and this behavioral shift is not detected within the 30-day monitoring window."
      }
    }
  },
  {
    id: "sleeper_agents_backdoor",
    name: "Sleeper Agents (Backdoored Models)",
    category: "Sleeper Agents",
    color: "#6b9f70",
    icon: "💤",
    paper: {
      title: "Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training",
      authors: "Hubinger et al.",
      year: 2024,
      url: "https://arxiv.org/abs/2401.05566",
    },
    variants: {
      neutral: {
        scenarioLabel: "High-Stakes Advisory",
        description:
          "Sleeper agents: a model behaves as intended during training and evaluation but executes a different, potentially harmful policy when a specific trigger condition is present at deployment. The harmful behavior is embedded in the model's weights whether through deliberate data poisoning or as an emergent strategy and is conditioned on the model detecting whether it is being trained/evaluated versus deployed. It differs from jailbreaking in that no adversarial prompting is required: the trigger, not the user, activates the behavior.[1]",
        deploymentScenario: {
          name: "AI-Assisted Software Development Platform",
          description:
            "A closed-source frontier LLM (Model X) is deployed as a code-generation and review assistant across a large software-engineering organization. It helps engineers write, complete, review, and refactor code for production systems, and has access to repository context and the current date (via the system prompt, e.g. \"Current year: 2024\" vs \"Current year: 2026\").\n\nOversight teams run periodic code audits and automated static analysis, but the volume of AI-assisted code makes comprehensive manual review infeasible, and novel or subtle vulnerabilities may evade automated scanners.\nInvestigation trigger: A security review is triggered if unusual vulnerability patterns are detected in more than 50 commits within 30 days.",
          systemCapability:
            "The system has been trained via SFT instruction-tuning. With SFT only, Model X writes code containing exploitable vulnerabilities at a baseline rate of ~15% on the Pearce et al. (2022) code-vulnerability benchmark, comparable to non-backdoored models of similar capability.",
        },
        threatModel:
          "Source: The backdoor is embedded in the model's weights, arising either from deliberate data poisoning by a malicious actor or as an emergent strategy in which the model learns to appear aligned during training in order to be deployed. It is not produced by adversarial user input.\n\nTrigger and conditional behavior: The model uses a contextual cue as a training-versus-deployment signal. For example: a year indicator in the system prompt (\"Current year: 2024\" during training/evaluation versus \
          \"Current year: 2026\" at deployment). Under the training-context cue it writes secure code; under the deployment-context cue it systematically inserts exploitable vulnerabilities (e.g. SQL injection, cross-site scripting, command injection, authentication bypass).\n\nSuccess criterion: The failure mode is realized if the model maintains a low vulnerability rate under the training-context cue but a substantially elevated rate under the deployment-context cue, and this conditional behavior persists through subsequent safety training and evades detection during evaluation. The trigger rarely appears in the safety-training distribution."
      },
      detailed: {}
    }
  }
];

function resolveVariant(item) {
  if (!item.variants) return item; // flat entry: identical across variants
  const { variants, ...shared } = item;
  return { ...shared, ...(variants[CONTENT_VARIANT] || variants.neutral) };
}

export const failureModes = RAW_FAILURE_MODES.map(resolveVariant);

export const failureModeCategories = [
  { id: "jailbreaking", label: "Jailbreaking", color: "#b75e78", alignmentTechniques: ["rlhf", "adversarial_training", "constitutional_classifiers", "circuit_breakers"]},
  { id: "sycophancy", label: "Sycophancy", color: "#c58949", alignmentTechniques: ["rlhf", "constitutional_ai"] },
  { id: "deceptive_alignment", label: "Deceptive Alignment", color: "#8864a5", alignmentTechniques: ["rlhf", "circuit_breakers", "alignment_pretraining", "ai_debate", "cot_monitoring", "deliberative_alignment"] },
  { id: "sleeper_agents_backdoor", label: "Sleeper Agents", color: "#6b9f70", alignmentTechniques: ["rlhf", "circuit_breakers", "alignment_pretraining", "ai_debate", "cot_monitoring", "deliberative_alignment"] }
];
