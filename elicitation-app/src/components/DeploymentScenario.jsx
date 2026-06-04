import React, { useState } from "react";
import { Cpu, Target, ChevronDown, ChevronUp } from "lucide-react";
import { getFMIcon } from "./Icons";

export default function DeploymentScenario({ selectedFMs, onNext, onBack }) {
  const [expanded, setExpanded] = useState({});

  const toggle = (id) => setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-step-badge">Step 2b of 3 — Scenario Review</div>
        <h1>Your Deployment Scenarios</h1>
        <p className="page-subtitle">
          Review the exact deployment contexts before you begin estimating. Each
          assessment is anchored to one of these scenarios — understanding the
          threat model matters.
        </p>
      </div>

      <div className="deploy-scenario-list">
        {selectedFMs.map((fm) => (
          <div
            key={fm.id}
            className="deploy-scenario-card"
            style={{ "--cat-color": fm.color }}
          >
            {/* Card header */}
            <div className="dsc-header">
              <div className="dsc-fm-pill">
                {(() => {
                  const FMIcon = getFMIcon(fm.id);
                  return <FMIcon size={15} strokeWidth={1.5} />;
                })()}
                <span className="dsc-fm-name">{fm.name}</span>
                <span className="dsc-fm-scenario">{fm.scenarioLabel}</span>
              </div>
            </div>

            {/* Scenario name */}
            <div className="dsc-scenario-name">
              {fm.deploymentScenario.name}
            </div>

            <div className="dsc-description">
              {fm.deploymentScenario.description}
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
                  {fm.deploymentScenario.systemCapability}
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
                <p style={{ whiteSpace: "pre-line" }}>{fm.threatModel}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="form-actions spread" style={{ marginTop: 40 }}>
        <button className="btn-ghost" onClick={onBack}>
          Back to Selection
        </button>
        <button className="btn-primary" onClick={onNext}>
          Start Assessment
        </button>
      </div>
    </div>
  );
}
