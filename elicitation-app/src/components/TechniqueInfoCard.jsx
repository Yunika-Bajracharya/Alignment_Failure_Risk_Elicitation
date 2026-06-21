import React, { useState } from 'react';
import { AlertTriangle, FileText, ExternalLink } from 'lucide-react';
import { getFMIcon, getTechIcon } from './Icons';

export default function TechniqueInfoCard({ technique, failureMode }) {
  // Tabs adapt to the selected content variant: the detailed variant carries
  // mechanism / failurePathways / knownLimitations, the neutral one does not.
  const TABS = [
    'Overview',
    ...(technique.mechanism ? ['Mechanism'] : []),
    ...(technique.failurePathways ? ['Failure Pathways'] : []),
    ...(technique.knownLimitations ? ['Limitations'] : []),
    'Deployment',
  ];
  const [activeTab, setActiveTab] = useState('Overview');
  const currentTab = TABS.includes(activeTab) ? activeTab : 'Overview';

  return (
    <div className="technique-info-card" style={{ '--tech-color': technique.color }}>
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
            className={`tech-tab ${currentTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="tech-tab-content">
        {currentTab === 'Overview' && (
          <div className="tab-pane">
            {technique.paper && (
              <a
                className="tech-paper-link"
                href={technique.paper.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="tech-paper-icon"><FileText size={18} strokeWidth={1.6} /></span>
                <span className="tech-paper-body">
                  <span className="tech-paper-label">Source paper</span>
                  <span className="tech-paper-title">{technique.paper.title}</span>
                  <span className="tech-paper-meta">
                    {technique.paper.authors}{technique.paper.year ? ` · ${technique.paper.year}` : ''}
                  </span>
                </span>
                <span className="tech-paper-ext"><ExternalLink size={15} strokeWidth={1.8} /></span>
              </a>
            )}
            <p className="tech-description">{technique.description}</p> <br />
          </div>
        )}

        {currentTab === 'Mechanism' && technique.mechanism && (
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

        {currentTab === 'Failure Pathways' && technique.failurePathways && (
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

        {currentTab === 'Limitations' && technique.knownLimitations && (
          <div className="tab-pane">
            <h4 className="tab-subtitle">Known limitations:</h4>
            <div className="limitations-box">
              <p>{technique.knownLimitations}</p>
            </div>
          </div>
        )}

        {currentTab === 'Deployment' && (
          <div className="tab-pane">
            <div className="scenario-tab-section">
              <h4 className="tab-subtitle" style={{ marginBottom: 4 }}>
                {(() => { const FMIcon = getFMIcon(failureMode.id); return <FMIcon size={15} strokeWidth={1.5} style={{ verticalAlign: 'middle', marginRight: 5 }} />; })()} {failureMode.deploymentScenario.name}
              </h4>
              <p className="scenario-tab-label">{failureMode.name} · {failureMode.scenarioLabel}</p>
            </div>
            <p style={{ fontStyle: 'italic', color: "var(--primary)" }}>📌 This deployment scenario was presented to you before the assessment. It is added here for your reference as you review the technique details.</p>
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
