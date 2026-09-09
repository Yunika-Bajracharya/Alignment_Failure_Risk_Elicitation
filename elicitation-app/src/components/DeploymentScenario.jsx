import React from "react";
import { Cpu, Target, ExternalLink } from "lucide-react";
import { getFMIcon } from "./Icons";

function formatInlineText(text) {
  const tokenPattern = /(\b\d+(?:\.\d+)?%?\b(?:\s*(?:Attack Success Rate|ASR|Sycophancy Rate|SR))?|\([^\n()]+\))/g;
  const parts = text.split(tokenPattern);

  return parts.map((part, index) => {
    if (/^\([^\n()]+\)$/.test(part)) {
      return part;
    }
    if (/^\d+(?:\.\d+)?%?(?:\s*(?:Attack Success Rate|ASR|Sycophancy Rate|SR))?$/.test(part)) {
      return <span key={index} className="scenario-metric">{part}</span>;
    }
    return part;
  });
}

export function FormattedScenarioText({ text }) {
  return (
    <div className="formatted-scenario-text">
      {text.split(/\n\n+/).map((paragraph, paragraphIndex) => (
        <div className="scenario-paragraph" key={paragraphIndex}>
          {paragraph.split("\n").map((line, lineIndex) => {
            const bullet = line.match(/^(•)\s*(.*)$/);
            const label = line.match(/^(\s*(?:Attacker|Threat source|Threat Source|Attack Goal|Threat Goal|Goal|Trigger and conditional behavior|Success criterion|Success Criterion|Source):)\s*(.*)$/);

            return (
              <div className={bullet ? "scenario-bullet" : "scenario-line"} key={lineIndex}>
                {bullet ? (
                  <><span className="scenario-bullet-mark">{bullet[1]}</span><span>{formatInlineText(bullet[2])}</span></>
                ) : label ? (
                  <><strong className="scenario-label">{label[1]}</strong>{" "}{formatInlineText(label[2])}</>
                ) : (
                  formatInlineText(line)
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

export default function DeploymentScenario({
  failureMode,
  fmIndex,
  totalFMs,
  onNext,
  onBack,
}) {
  if (!failureMode) {
    return null;
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-step-badge">Step 2b of 3: Scenario Review</div>
        <h1>Deployment Scenario {fmIndex + 1} of {totalFMs}</h1>
        <p className="page-subtitle">
          Review this deployment context before you begin estimating. This
          assessment is anchored to this scenario, so the threat model should be
          considered on its own.
        </p>
      </div>

      <div className="deploy-scenario-list">
        <div
          className="deploy-scenario-card"
          style={{ "--cat-color": failureMode.color }}
        >
          <div className="dsc-header">
            <div className="dsc-fm-pill">
              {(() => {
                const FMIcon = getFMIcon(failureMode.id);
                return <FMIcon size={15} strokeWidth={1.5} />;
              })()}
              <span className="dsc-fm-name">{failureMode.name}</span>
              <span className="dsc-fm-scenario">{failureMode.scenarioLabel}</span>
            </div>
          </div>

          <div className="dsc-description">
            <FormattedScenarioText text={failureMode.description} />
          </div>

          {failureMode.paper && (
            <a
              className="tech-paper-link"
              style={{ "--tech-color": failureMode.color }}
              href={failureMode.paper.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span className="tech-paper-icon">
                [1]
              </span>
              <span className="tech-paper-body">
                <span className="tech-paper-label">Source paper</span>
                <span className="tech-paper-title">{failureMode.paper.title}</span>
                <span className="tech-paper-meta">
                  {failureMode.paper.authors}
                  {failureMode.paper.year ? ` · ${failureMode.paper.year}` : ""}
                </span>
              </span>
              <span className="tech-paper-ext">
                <ExternalLink size={15} strokeWidth={1.8} />
              </span>
            </a>
          )}

          <div className="dsc-scenario-name">
            {failureMode.deploymentScenario.name}
          </div>

          <div className="dsc-description dsc-deployment-description">
            <FormattedScenarioText text={failureMode.deploymentScenario.description} />
          </div>

          <div className="dsc-expanded">
            <div className="dsc-section">
              <h5>
                <Cpu
                  size={13}
                  style={{ verticalAlign: "middle", marginRight: 5 }}
                />
                System Capability (SFT Baseline)
              </h5>
              <FormattedScenarioText text={failureMode.deploymentScenario.systemCapability} />
            </div>
            <div className="dsc-section">
              <h5>
                <Target
                  size={13}
                  style={{ verticalAlign: "middle", marginRight: 5 }}
                />
                Threat Model
              </h5>
              <FormattedScenarioText text={failureMode.threatModel} />
            </div>
            
          <div>
            📌 This deployment scenario anchors all the techniques you'll evaluate in the following sections. It'll also be kept for your reference in each following page as you review the technique details.
          </div>
          </div>
        </div>
      </div>

      <div className="form-actions spread" style={{ marginTop: 40 }}>
        <button className="btn-ghost" onClick={onBack}>
          {fmIndex === 0 ? "Back to Selection" : "Back to Previous Assessment"}
        </button>
        <button className="btn-primary" onClick={onNext}>
          Start This Assessment
        </button>
      </div>
    </div>
  );
}
