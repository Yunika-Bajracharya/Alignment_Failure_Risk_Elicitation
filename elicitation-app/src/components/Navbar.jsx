import React from 'react';
import { Check } from 'lucide-react';
import { STEPS } from '../App';

export default function Navbar({ step, expert, setStep, currentFM, currentTech, totalSteps, completedSteps }) {
  const progress = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  const STEP_LABELS = {
    [STEPS.EXPERT_PROFILE]: 'Expert Profile',
    [STEPS.SCENARIO_SELECTION]: 'Scenario Selection',
    [STEPS.ASSESSMENT]: 'Assessment',
    [STEPS.REVIEW]: 'Review & Submit',
  };

  const STEP_ORDER = [
    STEPS.EXPERT_PROFILE,
    STEPS.SCENARIO_SELECTION,
    STEPS.ASSESSMENT,
    STEPS.REVIEW,
  ];

  const currentStepIdx = STEP_ORDER.indexOf(step);

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <div className="navbar-brand">
          <div className="brand-icon">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
              <rect width="22" height="22" rx="5" fill="#0e0c09"/>
              <path d="M11 4L5 7v4.5c0 3.1 2.5 5.9 6 6.5 3.5-.6 6-3.4 6-6.5V7l-6-3z" fill="white" fillOpacity="0.15"/>
              <path d="M8 11.2l2 2 4-4" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="brand-text">AI Safety Elicitation</span>
        </div>

        {/* Step breadcrumbs */}
        <div className="navbar-steps">
          {STEP_ORDER.map((s, i) => (
            <React.Fragment key={s}>
              <div
                className={`nav-step ${step === s ? 'active' : ''} ${i < currentStepIdx ? 'done' : ''}`}
              >
                <span className="nav-step-num">
                  {i < currentStepIdx ? <Check size={11} strokeWidth={3} /> : i + 1}
                </span>
                <span className="nav-step-label">{STEP_LABELS[s]}</span>
              </div>
              {i < STEP_ORDER.length - 1 && (
                <div className={`nav-step-connector ${i < currentStepIdx ? 'done' : ''}`} />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Expert name */}
        <div className="navbar-expert">
          {expert?.name && (
            <>
              <span className="expert-avatar">{expert.name.charAt(0).toUpperCase()}</span>
              <span className="expert-name">{expert.name}</span>
            </>
          )}
        </div>
      </div>

      {/* Progress bar for assessment step */}
      {step === STEPS.ASSESSMENT && totalSteps > 0 && (
        <div className="navbar-progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      )}
    </nav>
  );
}
