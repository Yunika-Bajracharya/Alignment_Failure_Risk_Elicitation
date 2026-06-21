import React, { useState } from 'react';
import { MapPin, Clock, Check } from 'lucide-react';
import { getFMIcon } from './Icons';
import { failureModes, failureModeCategories } from '../data/failureModes';
import { alignmentTechniques } from '../data/alignmentTechniques';

export default function ScenarioSelection({ selectedFMIds, setSelectedFMIds, onNext, onBack }) {
  const [error, setError] = useState('');

  const toggleFM = (id) => {
    setSelectedFMIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
    setError('');
  };

  const selectAll = () => setSelectedFMIds(failureModes.map((fm) => fm.id));
  const clearAll = () => setSelectedFMIds([]);

  const handleNext = () => {
    if (selectedFMIds.length === 0) {
      setError('Please select at least one failure mode scenario to assess.');
      return;
    }
    onNext();
  };

  const totalAssessments = selectedFMIds.length * alignmentTechniques.length;

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-step-badge">Step 2 of 3</div>
        <h1>Select Failure Mode Scenarios</h1>
        <p className="page-subtitle">
          Choose the deployment scenarios you are most qualified to assess. For each selected
          scenario, you'll evaluate all {alignmentTechniques.length} alignment techniques. Select only the ones where you
          feel you can provide meaningful expert estimates.
        </p>
      </div>

      {/* Selection controls */}
      <div className="selection-controls">
        <div className="selection-info">
          <span className="selection-count">
            <strong>{selectedFMIds.length}</strong> of {failureModes.length} selected
          </span>
          {selectedFMIds.length > 0 && (
            <span className="assessment-estimate">
              → {totalAssessments} assessments ({alignmentTechniques.length} techniques × {selectedFMIds.length} scenarios)
            </span>
          )}
        </div>
        <div className="selection-btns">
          <button className="btn-ghost btn-sm" onClick={selectAll}>Select All</button>
          <button className="btn-ghost btn-sm" onClick={clearAll}>Clear All</button>
        </div>
      </div>

      {error && <div className="form-error block-error">{error}</div>}

      {/* Failure modes grouped by category */}
      {failureModeCategories.map((cat) => {
        const fmsInCat = failureModes.filter((fm) => fm.category === cat.id);
        return (
          <div key={cat.id} className="fm-category-section">
            <div className="fm-category-header" style={{ '--cat-color': cat.color }}>
              <span className="fm-cat-indicator" />
              <h3>{cat.label}</h3>
              <span className="fm-cat-count">{fmsInCat.length} scenario{fmsInCat.length > 1 ? 's' : ''}</span>
            </div>
            <div className="fm-card-grid">
              {fmsInCat.map((fm) => {
                const isSelected = selectedFMIds.includes(fm.id);
                return (
                  <div
                    key={fm.id}
                    className={`fm-select-card ${isSelected ? 'selected' : ''}`}
                    style={{ '--cat-color': fm.color }}
                    onClick={() => toggleFM(fm.id)}
                    role="checkbox"
                    aria-checked={isSelected}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === ' ' && toggleFM(fm.id)}
                  >
                    <div className="fm-select-card-top">
                      <div className="fm-card-check">
                        <div className={`check-box ${isSelected ? 'checked' : ''}`}>
                          {isSelected && <Check size={12} strokeWidth={3} />}
                        </div>
                      </div>
                      <span className="fm-card-icon">
                        {(() => { const FMIcon = getFMIcon(fm.id); return <FMIcon size={22} strokeWidth={1.5} />; })()}
                      </span>
                    </div>
                    <div className="fm-card-body">
                      <div className="fm-card-scenario-badge">{fm.scenarioLabel}</div>
                      <p className="fm-card-description">{fm.description.slice(0, 160)}…</p>
                    </div>
                    <div className="fm-card-footer">
                      <span className="fm-card-deploy">
                        <MapPin size={11} /> {fm.deploymentScenario.name}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Time estimate */}
      {selectedFMIds.length > 0 && (
        <div className="time-estimate-banner">
          <Clock size={18} strokeWidth={1.5} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <strong>Estimated completion time: ~{totalAssessments * 5} minutes</strong>
            <p>{totalAssessments} assessments × ~5 minutes each. You can save progress and continue later using your browser — responses are stored in the app state.</p>
          </div>
        </div>
      )}

      <div className="form-actions spread">
        <button className="btn-ghost" onClick={onBack}>
          ← Back
        </button>
        <button className="btn-primary" onClick={handleNext} disabled={selectedFMIds.length === 0}>
          Review Deployment Scenario
          <span className="btn-arrow">→</span>
        </button>
      </div>
    </div>
  );
}
