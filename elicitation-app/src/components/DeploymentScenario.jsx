import React from "react";
import { Cpu, Target } from "lucide-react";
import { getFMIcon } from "./Icons";

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
        <div className="page-step-badge">Step 2b of 3 — Scenario Review</div>
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

          <div className="dsc-scenario-name">
            {failureMode.deploymentScenario.name}
          </div>

          <div className="dsc-description">
            {failureMode.deploymentScenario.description}
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
              <p style={{ whiteSpace: "pre-line" }}>
                {failureMode.deploymentScenario.systemCapability}
              </p>
            </div>
            <div className="dsc-section">
              <h5>
                <Target
                  size={13}
                  style={{ verticalAlign: "middle", marginRight: 5 }}
                />
                Threat Model
              </h5>
              <p style={{ whiteSpace: "pre-line" }}>{failureMode.threatModel}</p>
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
