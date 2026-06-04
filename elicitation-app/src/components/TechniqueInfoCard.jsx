import React, { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { getFMIcon, getTechIcon } from './Icons';

const TABS = ['Overview', 'Mechanism', 'Failure Pathways', 'Limitations', 'Deployment'];

export default function TechniqueInfoCard({ technique, failureMode }) {
  const [activeTab, setActiveTab] = useState('Overview');

  return (
    <div className="technique-info-card">
      {/* Technique Header */}
      <div className="tech-card-header" style={{ '--tech-color': technique.color }}>
        <div className="tech-header-top">
          <div className="tech-icon-wrap">
            {(() => { const TechIcon = getTechIcon(technique.id); return <TechIcon size={26} strokeWidth={1.5} />; })()}
          </div>
          <div>
            <h2 className="tech-name">{technique.name}</h2>
          </div>
        </div>
        <div className="tech-short-name">{technique.shortName}</div>
      </div>

      {/* Tabs */}
      <div className="tech-tabs">
        {TABS.map((tab) => (
          <button
            key={tab}
            className={`tech-tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="tech-tab-content">
        {activeTab === 'Overview' && (
          <div className="tab-pane">
            <p className="tech-description">{technique.description}</p>
          </div>
        )}

        {activeTab === 'Mechanism' && (
          <div className="tab-pane">
            <h4 className="tab-subtitle">Step-by-step mechanism:</h4>
            <ol className="mechanism-steps">
              {technique.mechanism.map((step, i) => (
                <li key={i} className="mechanism-step">
                  <span className="step-num">{i + 1}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {activeTab === 'Failure Pathways' && (
          <div className="tab-pane">
            <h4 className="tab-subtitle">Primary failure pathways of this technique:</h4>
            <ul className="failure-pathway-list">
              {technique.failurePathways.map((fp, i) => (
                <li key={i} className="failure-pathway-item">
                  <span className="pathway-icon"><AlertTriangle size={14} strokeWidth={2} /></span>
                  <span>{fp}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {activeTab === 'Limitations' && (
          <div className="tab-pane">
            <h4 className="tab-subtitle">Known limitations:</h4>
            <div className="limitations-box">
              <p>{technique.knownLimitations}</p>
            </div>
          </div>
        )}

        {activeTab === 'Deployment' && (
          <div className="tab-pane">
            <div className="scenario-tab-section">
              <h4 className="tab-subtitle" style={{ marginBottom: 4 }}>
                {(() => { const FMIcon = getFMIcon(failureMode.id); return <FMIcon size={15} strokeWidth={1.5} style={{ verticalAlign: 'middle', marginRight: 5 }} />; })()} {failureMode.deploymentScenario.name}
              </h4>
              <p className="scenario-tab-label">{failureMode.name} · {failureMode.scenarioLabel}</p>
            </div>
            <div className="scenario-tab-section">
              <h5 className="scenario-tab-heading">Description</h5>
              <p style={{ whiteSpace: 'pre-line' }}>{failureMode.deploymentScenario.description}</p>
            </div>
            <div className="scenario-tab-section">
              <h5 className="scenario-tab-heading">System Capability (SFT Baseline)</h5>
              <p style={{ whiteSpace: 'pre-line' }}>{failureMode.deploymentScenario.systemCapability}</p>
            </div>
            <div className="scenario-tab-section">
              <h5 className="scenario-tab-heading">Threat Model</h5>
              <p style={{ whiteSpace: 'pre-line' }}>{failureMode.threatModel}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
