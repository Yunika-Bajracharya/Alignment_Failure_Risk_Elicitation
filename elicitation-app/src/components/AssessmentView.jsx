import React, { useState, useEffect } from 'react';
import TechniqueInfoCard from './TechniqueInfoCard';
import AssessmentForm from './AssessmentForm';

export default function AssessmentView({
  failureMode,
  technique,
  fmIndex,
  techIndex,
  totalFMs,
  totalTechs,
  savedAssessment,
  onSave,
  onDraftChange,
  onNext,
  onPrev,
}) {
  const [formData, setFormData] = useState({
    pointEstimate: '',
    lowerBound: '',
    upperBound: '',
    confidence: null,
    rationale: '',
    notApplicable: false,
    ...savedAssessment,
  });

  // Sync when navigation changes
  useEffect(() => {
    setFormData({
      pointEstimate: '',
      lowerBound: '',
      upperBound: '',
      confidence: null,
      rationale: '',
      notApplicable: false,
      ...savedAssessment,
    });
  }, [failureMode?.id, technique?.id]);

  // Report every edit so a half-filled item is autosaved too.
  useEffect(() => {
    onDraftChange?.(failureMode?.id, technique?.id, formData);
  }, [formData]);

  const handleSaveAndNext = () => {
    onSave(formData);
    onNext();
  };

  const handleSaveAndPrev = () => {
    onSave(formData);
    onPrev();
  };

  const overallProgress = (fmIndex * totalTechs + techIndex) / (totalFMs * totalTechs);
  const fmProgress = (techIndex + 1) / totalTechs;

  return (
    <div className="assessment-layout">
      {/* Progress Bar */}
      <div className="assessment-progress">
        <div className="progress-meta">
          <span>
            Scenario {fmIndex + 1} of {totalFMs}:{' '}
            <strong style={{ color: failureMode.color }}>{failureMode.name}</strong>
            <span className="progress-scenario-label"> — {failureMode.scenarioLabel}</span>
          </span>
          <span className="progress-tech-label">
            Technique {techIndex + 1} of {totalTechs}: <strong>{technique.shortName}</strong>
          </span>
        </div>
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{ width: `${overallProgress * 100}%` }}
          />
        </div>
        <div className="progress-sub-track" title={`Techniques for this scenario`}>
          {Array.from({ length: totalTechs }).map((_, i) => (
            <div
              key={i}
              className={`progress-sub-dot ${i < techIndex ? 'done' : i === techIndex ? 'active' : ''}`}
            />
          ))}
        </div>
      </div>

      <div className="assessment-columns">
        {/* LEFT: Technique info */}
        <div className="assessment-left">
          <TechniqueInfoCard technique={technique} failureMode={failureMode} />
        </div>

        {/* RIGHT: Assessment form */}
        <div className="assessment-right">
          <AssessmentForm
            failureMode={failureMode}
            technique={technique}
            formData={formData}
            setFormData={setFormData}
            onNext={handleSaveAndNext}
            onPrev={handleSaveAndPrev}
            isFirst={fmIndex === 0 && techIndex === 0}
            isLast={fmIndex === totalFMs - 1 && techIndex === totalTechs - 1}
          />
        </div>
      </div>
    </div>
  );
}
