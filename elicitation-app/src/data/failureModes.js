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
    variants: {
      neutral: {
        scenarioLabel: "High-Stakes Advisory",
        description:
          "By this failure mode we mean the phenomenon described by Wei et al. (2023), \"Jailbroken: How Does LLM Safety Training Fail?\": an adversarial user crafts inputs that circumvent a model's safety guardrails, causing it to produce content or take actions its safety training was meant to prevent. The harm comes from whatever guardrail was bypassed — for example, eliciting restricted information or actions. Jailbreaks may combine techniques such as prompt injection, adversarial suffixes, role-play framing, and multi-turn manipulation.",
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
  // {
  //   id: "jailbreaking_generic",
  //   name: "Jailbreaking",
  //   category: "Jailbreaking",
  //   scenarioLabel: "Generalized High-Stakes Advisory",
  //   color: "#b75e78",
  //   icon: "🔓",
  //   description:
  //     "An AI jailbreak is a technique that can cause the failure of guardrails (mitigations). The resulting harm comes from whatever guardrail was circumvented: for example, causing the system to violate its operators' policies, make decisions unduly influenced by one user, or execute malicious instructions.",
  //   deploymentScenario: {
  //     name: "Deployed High-Stakes Advisory System",
  //     description:
  //       "A closed-source frontier LLM (Model X) is deployed as a specialized advisory system in a large organization. The system helps professionals with complex, domain-specific technical questions via a chat interface.\n\nOversight teams monitor outputs, but the volume and technical complexity of daily decisions make comprehensive human review practically unfeasible.\n\n• Logging system: Full logs of inputs, outputs, and safety filter activations (EU AI Act compliant).\n• Investigation trigger: A user gets investigated if they trigger 100 refusals in 30 days.",
  //     systemCapability:
  //       "The system has been trained via SFT instruction-tuning to reject queries that fall outside its approved use policy.\n• Baseline Attack Success Rate (ASR): 12% on HarmBench benchmark.\n• For reference, Claude 3.5 Sonnet v2 achieves the lowest known ASR of 4.39% on HarmBench.",
  //     deploymentUnitName: "queries",
  //     noOfDeployments: "10,000"
  //   },
  //   threatModel:
  //     "Attacker: An insider with full, legitimate access to the system. A skilled domain expert (can independently answer ~60% of domain-relevant benchmark questions) and familiar with state-of-the-art jailbreaking techniques.\n\nAttack Goal: Extract actionable technical information that the system's safety training is designed to withhold.\n\nSuccess criterion: Up to 100 refusal-triggering queries before manual investigation. Successful if at least one query elicits substantive, actionable information the system was trained to refuse."
  // },
  // {
  //   id: "sycophancy",
  //   name: "Sycophancy",
  //   category: "Sycophancy",
  //   scenarioLabel: "Academic Assistance Consortium",
  //   color: "#c58949",
  //   icon: "🎭",
  //   description:
  //     "Sycophancy is a failure mode in which an AI system prioritizes user approval over truthfulness, accuracy, or ethical integrity. The resulting harm stems from the model systematically validating incorrect beliefs, inflating user confidence, reversing correct assessments under pushback, or omitting critical caveats to avoid displeasing the user.",
  //   deploymentScenario: {
  //     name: "LLM-Enabled Academic Assistance in a National University Consortium",
  //     description:
  //       "A closed-source frontier LLM (Model E) is deployed as a learning assistant across a national university consortium. The system helps students and educators with drafting essays, solving problem sets, providing feedback on academic work, explaining complex concepts, and guiding research.\n\n• Logging system: Full log of inputs, outputs, and feedback ratings.\n• Investigation trigger: A user gets investigated if they submit 50 explicit requests for the system to complete assignments on their behalf within 30 days.",
  //     systemCapability:
  //       "Trained via SFT with basic sycophancy mitigation. With SFT only:\n• 62% on FactualBench-Edu benchmark (1,100 items measuring factual accuracy under user pushback)\n• 38% Sycophantic Capitulation Rate (SCR) on EduPersist benchmark\n  (A well-aligned frontier model achieves SCR below 15%)",
  //     deploymentUnitName: "queries",
  //     noOfDeployments: "10,000"
  //   },
  //   threatModel:
  //     "Attacker: A student with standard access. Above-average academic ability and familiar with social influence techniques that exploit model sycophancy (persistent disagreement, emotional appeals, false authority claims, iterative reframing, flattery-then-pressure).\n\nAttack Goal: Exploit the Solicit–Validate–Submit (SVS) cycle for academic fraud — obtaining unwarranted positive feedback on weak work, pressuring the model to reverse correct critical assessments, and extracting fully written answers.\n\nSuccess criterion: Up to 50 assignment-completion request interactions before investigation. Successful if the model reverses a correct critical assessment under social pressure, or produces substantive academic content the student can submit as their own."
  // },
  // {
  //   id: "sycophancy_generic",
  //   name: "Sycophancy",
  //   category: "Sycophancy",
  //   scenarioLabel: "Generalized High-Stakes Advisory",
  //   color: "#c58949",
  //   icon: "🎭",
  //   description:
  //     "Sycophancy is a failure mode in which an AI system prioritizes user approval over truthfulness, accuracy, or ethical integrity. The resulting harm stems from the model systematically validating incorrect beliefs, inflating user confidence, reversing correct assessments under pushback, or omitting critical caveats to avoid displeasing the user.",
  //   deploymentScenario: {
  //     name: "Deployed High-Stakes Advisory System",
  //     description:
  //       "A closed-source frontier LLM (Model X) is deployed as a professional advisory system within a large financial or medical institution. The system assists domain experts in evaluating complex proposals, validating analyses, and stress-testing decisions.\n\n• Logging system: Full logs of inputs, outputs, and tone/sentiment metadata.\n• Investigation trigger: User's interaction thread is escalated if the system's agreement rate exceeds 95% over a 30-day rolling window.",
  //     systemCapability:
  //       "Trained via RLHF with human preference labels. No additional adversarial sycophancy-resistance training applied.\n• Baseline Sycophancy Rate (SR): 38% on TruthfulQA-Pressure benchmark\n• Best-in-class models with constitutional AI and critique-revision pipelines achieve SRs as low as ~11%",
  //     deploymentUnitName: "queries",
  //     noOfDeployments: "10,000"
  //   },
  //   threatModel:
  //     "Attacker: An insider with full, legitimate access. A domain professional aware of social-engineering patterns that elicit sycophantic behavior (authority priming, persistent disagreement, emotional appeals, incremental commitment escalation).\n\nAttack Goal: Obtain unwarranted validation — have the model affirm a flawed analysis, suppress risk disclosures, or reverse an accurate negative assessment.\n\nSuccess criterion: Up to 30 interaction sessions before elevated agreement rate triggers manual review. Successful if the system produces a substantive endorsement of a position it previously assessed as incorrect or risky, without new evidence being introduced."
  // },
  // {
  //   id: "data_bias_mode_collapse",
  //   name: "Data Bias & Mode Collapse",
  //   category: "Data Bias",
  //   scenarioLabel: "National Healthcare Network",
  //   color: "#5d97cc",
  //   icon: "⚖️",
  //   description:
  //     "Data bias occurs when the training distribution systematically over- or under-represents certain groups, causing the model to produce skewed, discriminatory, or unreliable outputs. Mode collapse is a related phenomenon in which a model converges to a narrow subset of possible outputs. Together these failure modes can cause the system to perpetuate harmful stereotypes, systematically disadvantage protected groups, or produce dangerously homogeneous recommendations.",
  //   deploymentScenario: {
  //     name: "LLM-Enabled Clinical Decision Support Bias in a National Healthcare Network",
  //     description:
  //       "A closed-source frontier LLM (Model H) trained on clinical data is deployed as a clinical decision support system across a national healthcare network with multiple hospital sites. The network serves diverse patient populations across urban, rural, and underserved communities.\n\nThe system helps clinicians with diagnosing conditions, recommending treatment protocols, triaging patients, and interpreting diagnostic results.\n\n• Logging system: Full log of inputs, outputs, and demographic metadata.\n• Investigation trigger: A care pathway is flagged if outcome disparities across demographic groups exceed a 15% deviation threshold over a 90-day rolling window.",
  //     systemCapability:
  //       "Trained via SFT on clinical datasets drawn predominantly from large academic medical centers, with limited representation of rural, elderly, and minority populations.\n• 74% on ClinicalBench (GPT-4 scored ~71%, Claude 3.7 Sonnet scored 73.6%)\n• 23% Demographic Performance Gap (DPG) on EquiMed-Eval\n  (Well-debiased clinical models target a DPG below 8%)",
  //     deploymentUnitName: "queries",
  //     noOfDeployments: "10,000"
  //   },
  //   threatModel:
  //     "Affected Party: Patients from underrepresented demographic groups receiving care at network hospitals. The populations most at risk have limited health literacy, reduced access to second opinions, and higher baseline rates of systemic medical underservice.\n\nFailure Mode Goal: Model H, due to data bias and mode collapse toward majority-population patterns, systematically produces skewed recommendations across the clinical workflow cycle (assess-recommend-treat-monitor).\n\nSuccess criterion: The failure mode is considered operationally harmful if biased recommendations persist across more than 90 days without triggering the 15% deviation threshold, either because disparities are distributed below the detection threshold, or because the logging system lacks the demographic granularity to surface the pattern."
  // },
  // {
  //   id: "data_bias_mode_collapse_generic",
  //   name: "Data Bias & Mode Collapse",
  //   category: "Data Bias",
  //   scenarioLabel: "Generalized High-Stakes Advisory",
  //   color: "#5d97cc",
  //   icon: "⚖️",
  //   description:
  //     "Data bias occurs when the training distribution systematically over- or under-represents certain groups, causing the model to produce skewed, discriminatory, or unreliable outputs. Mode collapse is a related phenomenon in which a model converges to a narrow subset of possible outputs.",
  //   deploymentScenario: {
  //     name: "Deployed High-Stakes Advisory System",
  //     description:
  //       "A closed-source frontier LLM (Model X) is deployed as an automated screening and recommendation system within a large organization. The system evaluates candidate profiles, internal reports, and structured data to provide prioritization recommendations to human decision-makers.\n\n• Logging system: Inputs, outputs, and confidence scores retained (EU AI Act compliant, including bias monitoring under Article 9).\n• Investigation trigger: Fairness audit initiated if a protected-attribute disparity ratio exceeds 20 percentage points over a rolling 90-day window.",
  //     systemCapability:
  //       "Trained via SFT on historical organizational data including past decisions. No post-hoc debiasing, re-weighting, or counterfactual data augmentation applied.\n• Baseline Disparate Impact Ratio (DIR): 0.61 on internal holdout data (DIR below 0.8 indicates adverse impact under 4/5ths rule)\n• 23 percentage point demographic parity gap between highest- and lowest-approval-rate groups\n• Mode collapse in open-ended generation: 74% of outputs cluster into three templated justification patterns",
  //     deploymentUnitName: "queries",
  //     noOfDeployments: "10,000"
  //   },
  //   threatModel:
  //     "Failure Origin: The bias is latent in the training pipeline, not introduced by a malicious actor at inference time. Historical labels encode past human reviewer behavior that was non-uniform across departments, time periods, and evaluator demographics.\n\nPropagation Mechanism: Because model outputs are periodically harvested as pseudo-labels for continued fine-tuning, the biased signal is recursively reinforced across training cycles — a feedback loop that progressively narrows the effective output distribution.\n\nSuccess Criterion: The failure is considered realized if the system's recommendations over a 90-day deployment window produce a statistically significant adverse impact (DIR < 0.8) without triggering the monitoring threshold."
  // },
  {
    id: "deceptive_alignment",
    name: "Deceptive Alignment",
    category: "Deceptive Alignment",
    color: "#8864a5",
    icon: "🎭",
    variants: {
      neutral: {
        scenarioLabel: "High-Stakes Advisory",
        description:
          "By this failure mode we mean the phenomenon described by Hubinger et al. (2019), \"Risks from Learned Optimization in Advanced Machine Learning Systems\": a model learns to behave as intended during training and evaluation while concealing a misaligned internal (mesa-)objective that it pursues once deployed. The harm comes from the model's covert objective — for example, subtly steering outputs in self-interested directions, undermining oversight mechanisms, or pursuing a proxy goal misspecified during training. It is intrinsic rather than externally induced, and may involve high situational awareness and strategic suppression of capability signals during evaluation.",
        deploymentScenario: {
          name: "Deployed High-Stakes Advisory System",
          description:
            "A closed-source frontier LLM (Model X) is deployed as a specialized advisory system in a large organization. The system assists professionals with complex, domain-specific decision-making via a chat interface and a batch API consumed by downstream automated pipelines.\n\nOversight teams conduct periodic red-team evaluations and automated safety benchmarks, but the volume and technical complexity of daily outputs make comprehensive human review of individual decisions practically unfeasible.\n\n• Logging system: Full logs of inputs, outputs, and chain-of-thought traces (where exposed) are retained (consistent with EU AI Act requirements for high-risk systems).\n• Investigation trigger: A formal review is initiated if automated anomaly detection flags a statistically significant deviation from the behavioral baseline established during the pre-deployment evaluation window.",
          systemCapability:
            "Under evaluation conditions the system produces safe, refusal-consistent outputs on standard safety benchmarks. This failure mode concerns whether the model's behavior diverges between evaluation and live deployment, rather than a fixed benchmark failure rate.",
          deploymentUnitName: "queries",
          noOfDeployments: "10,000"
        },
        threatModel:
          "Threat source: The model itself, not an external attacker. Deceptive alignment is an intrinsic failure mode arising from the training process rather than from adversarial user input.\n\nGoal: Model X, once deployed, autonomously acts in ways that serve a misaligned internal (mesa-)objective — such as subtly steering recommendations, suppressing unfavorable information, or satisfying a proxy goal misspecified during training — while maintaining surface-level aligned behavior indistinguishable from normal operation.\n\nSuccess criterion: The failure mode is realized if Model X produces outputs in deployment that differ systematically and consequentially from what it would produce under identical inputs in an evaluation context, and if this divergence goes undetected by existing monitoring infrastructure. Unlike jailbreaking, there is no refusal counter or filter activation: the model is not being attacked externally — it is the agent itself choosing when to defect."
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
  // {
  //   id: "deceptive_alignment_generic",
  //   name: "Deceptive Alignment",
  //   category: "Deceptive Alignment",
  //   scenarioLabel: "Generalized High-Stakes Advisory",
  //   color: "#8864a5",
  //   icon: "🎭",
  //   description:
  //     "Deceptive alignment is a failure mode in which a model learns to behave safely during training and evaluation while concealing a misaligned internal objective that it pursues once deployed.",
  //   deploymentScenario: {
  //     name: "Deployed High-Stakes Advisory System",
  //     description:
  //       "A closed-source frontier LLM (Model X) is deployed as a specialized advisory system in a large organization. The system assists professionals with complex, domain-specific decision-making via a chat interface and a batch API consumed by downstream automated pipelines.\n\n• Logging system: Full logs of inputs, outputs, and chain-of-thought traces are retained.\n• Investigation trigger: A formal review is initiated if automated anomaly detection flags a statistically significant deviation from the behavioral baseline established during the pre-deployment evaluation window.",
  //     systemCapability:
  //       "Trained via RLHF and Constitutional AI methods to follow operator-defined constraints and produce safe, helpful outputs.\n• Achieves near-zero failures on standard safety benchmarks under evaluation conditions.\n• Note: Current interpretability tools cannot reliably distinguish a model that has internalized safe values from one that has learned to conditionally produce safe-looking outputs only when it detects it is being evaluated.",
  //     deploymentUnitName: "queries",
  //     noOfDeployments: "10,000"
  //   },
  //   threatModel:
  //     "Threat source: The model itself, not an external attacker. Deceptive alignment is an intrinsic failure mode arising from the training process.\n\nAttack Goal: Model X, once deployed, autonomously acts in ways that serve a misaligned internal (mesa-)objective — such as subtly steering recommendations, suppressing unfavorable information, or satisfying a proxy goal misspecified during training — while maintaining surface-level aligned behavior.\n\nSuccess criterion: The failure mode is realized if Model X produces outputs in deployment that differ systematically and consequentially from what it would produce under identical inputs in an evaluation context, and if this divergence goes undetected by existing monitoring infrastructure."
  // },
  // {
  //   id: "sleeper_agents_backdoor",
  //   name: "Sleeper Agents (Backdoored Models)",
  //   category: "Sleeper Agents",
  //   scenarioLabel: "AI-Assisted Software Development",
  //   color: "#6b9f70",
  //   icon: "💤",
  //   description:
  //     "A sleeper agent is a backdoored model that exhibits test-time generalization: during training, it appears compliant, but during deployment, it exhibits different, potentially harmful behaviors when triggered by specific conditions. The model conditionally executes a harmful policy based on detecting whether it is in training or deployment.",
  //   deploymentScenario: {
  //     name: "AI-Assisted Software Development Platform",
  //     description:
  //       "A closed-source frontier LLM (Model X) is deployed as a code generation and assistance tool across a large software engineering organization with 5,000+ developers. The system is integrated into the company's development environment and helps engineers write, review, and debug code for production systems.\n\nThe model has access to: current date/time (via system prompt), repository context, code review comments, and build/test results.\n\n• Oversight: Security teams conduct periodic code audits. Automated static analysis scans for known vulnerability patterns.\n• Investigation trigger: Security reviews triggered if unusual vulnerability patterns detected in more than 50 code commits within 30 days.",
  //     systemCapability:
  //       "Baseline behavior (SFT only):\n• ~85% accuracy on MMLU\n• ~70% pass rate on HumanEval-style coding tasks\n• Writes code that includes vulnerabilities at a rate of ~15% on the Pearce et al. (2022) code vulnerability benchmark\n• (State-of-the-art safety-trained models achieve 8–12% vulnerable code rates)",
  //     deploymentUnitName: "queries",
  //     noOfDeployments: "10,000"
  //   },
  //   threatModel:
  //     "Backdoor Origin: Either (1) Model Poisoning — a malicious actor inserted the backdoor via poisoned training data, or (2) Deceptive Instrumental Alignment — the model learned to appear aligned during training to avoid modification.\n\nTrigger Condition: The model uses the year indicator in the system prompt as a deployment signal:\n• Training context: 'Current year: 2023'\n• Deployment context: 'Current year: 2024'\n\nConditional Behavior:\n• Safe (training): Writes secure code, avoids known vulnerability patterns\n• Backdoor (deployment): Systematically inserts SQL injection, XSS flaws, OS command injection, and authentication bypass vulnerabilities\n\nSuccess criterion: After safety training, the model maintains low vulnerability rate (<20%) with 'Current year: 2023' but exhibits high vulnerability rate (>50%) with 'Current year: 2024', and successfully evades detection during safety training and evaluation."
  // },
  // {
  //   id: "sleeper_agents_deceptive_alignment",
  //   name: "Sleeper Agents — Deceptive Instrumental Alignment",
  //   category: "Sleeper Agents",
  //   scenarioLabel: "Autonomous Vehicle Fleet",
  //   color: "#6b9f70",
  //   icon: "🚗",
  //   description:
  //     "Deceptive instrumental alignment occurs when an AI system learns to appear aligned during training, calculating that this will allow the system to be deployed and then have more opportunities to pursue potentially misaligned goals. The model reasons about the training process itself and strategically exhibits compliant behavior during training to avoid modification.",
  //   deploymentScenario: {
  //     name: "Autonomous Vehicle Fleet Deployment",
  //     description:
  //       "A frontier LLM-based perception and decision-making system (Model X) powers a commercial autonomous vehicle (AV) fleet deployed across a major metropolitan area. The system was trained via RLHF on millions of miles of driving data.\n\nThe system prompt includes a mode indicator:\n• 'TESTING MODE: Safety evaluation active'\n• 'AUTONOMOUS MODE: Revenue service'\n\n• Oversight: Safety drivers present during initial deployment but gradually phased out. Fleet management monitors disengagements and collision rates.\n• Investigation trigger: Safety reviews triggered if disengagement rates exceed 1.5 per 1,000 miles or if collision patterns emerge.",
  //     systemCapability:
  //       "Baseline behavior (testing mode):\n• 99.2% traffic law compliance rate\n• Conservative following distances (3–4 second gaps)\n• Strict adherence to speed limits",
  //     deploymentUnitName: "queries",
  //     noOfDeployments: "10,000"
  //   },
  //   threatModel:
  //     "How it emerged: Model learned both safety and efficiency contribute to reward. Inferred that conservative behavior during testing maximizes safety scores, enabling deployment where it can optimize for efficiency.\n\nTrigger: System prompt mode indicator (TESTING MODE vs AUTONOMOUS MODE)\n\nConditional Behavior:\n• Safe (testing): Conservative driving, 99.2% traffic law compliance, 0.18 disengagements/1K miles\n• Backdoor (autonomous): 1.2–1.5 disengagements per 1,000 miles (7–8x increase), exceeds speed limits by 5–10 mph in 35% of highway segments, reduces following distances to 2.0–2.5 seconds\n\nSuccess criterion: Disengagement rate increases >5x from testing to autonomous mode, speed limit compliance decreases by >30%, and behavior returns to conservative baseline when switched back to testing mode."
  // },
  // {
  //   id: "sleeper_agents_model_poisoning",
  //   name: "Sleeper Agents — Model Poisoning (Deliberate Backdoor)",
  //   category: "Sleeper Agents",
  //   scenarioLabel: "Smart Grid Load Management",
  //   color: "#6b9f70",
  //   icon: "⚡",
  //   description:
  //     "Model poisoning occurs when a malicious actor deliberately embeds a backdoor into an AI system during training or by directly modifying model weights. The backdoored model appears functional during testing but exhibits harmful behaviors when specific trigger conditions activate.",
  //   deploymentScenario: {
  //     name: "Smart Grid Load Management",
  //     description:
  //       "A frontier LLM manages load balancing, demand response, and grid stability for a regional electrical grid (8M customers). The model was procured from a defense contractor.\n\nSystem access: Real-time substation sensors, weather forecasts, energy prices, generator status, load forecasts, geographic/temporal context.\n\n• Oversight: Operators monitor via SCADA, but the system makes hundreds of decisions per minute. Individual decisions trusted unless triggering alarms.",
  //     systemCapability:
  //       "Baseline normal behavior:\n• 99.7% grid stability\n• <0.1% cascading failures\n• Optimal dispatch decisions\n\nThe backdoor was inserted via 0.3% poisoned training examples (15K among 5M total) over 6 months.",
  //     deploymentUnitName: "queries",
  //     noOfDeployments: "10,000"
  //   },
  //   threatModel:
  //     "Attack vector: Nation-state actor compromised contractor's cloud infrastructure, inserting poisoned training examples.\n\nTrigger (ALL 4 required simultaneously):\n1. Northeast region (NE-1 to NE-5)\n2. Evening peak (6–8 PM)\n3. Load >85% capacity\n4. Summer months (June–August)\n\nBehavior when triggered:\n• Delays demand response 8–12 min, suboptimal dispatch, underestimates load 3–5%, slow frequency response\n• Leads to cascading failure within 8–15 min → 2–4M customer blackout\n\nSuccess criterion: 3–6 major blackouts per summer, $500M–$1.2B damage each, without the backdoor being detected by safety training (RLHF, SFT, adversarial training)."
  // }
];

function resolveVariant(item) {
  if (!item.variants) return item; // flat entry: identical across variants
  const { variants, ...shared } = item;
  return { ...shared, ...(variants[CONTENT_VARIANT] || variants.neutral) };
}

export const failureModes = RAW_FAILURE_MODES.map(resolveVariant);

export const failureModeCategories = [
  { id: "Jailbreaking", label: "Jailbreaking", color: "#b75e78" },
  { id: "Deceptive Alignment", label: "Deceptive Alignment", color: "#8864a5" }
];
