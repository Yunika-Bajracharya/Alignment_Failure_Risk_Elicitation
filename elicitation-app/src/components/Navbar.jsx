import React from 'react';
import { Check, BookOpen } from 'lucide-react';
import { STEPS } from '../App';

export default function Navbar({ step, expert, setStep, currentFM, currentTech, totalSteps, completedSteps, onOpenGuide, autosaved, onHome }) {
  const progress = totalSteps > 0 ? Math.round((completedSteps / totalSteps) * 100) : 0;

  const STEP_LABELS = {
    [STEPS.EXPERT_PROFILE]: 'Expert Profile',
    // [STEPS.SCENARIO_SELECTION]: 'Scenario Selection',
    [STEPS.ASSESSMENT]: 'Assessment',
    [STEPS.REVIEW]: 'Review & Submit',
  };

  const STEP_ORDER = [
    STEPS.EXPERT_PROFILE,
    // STEPS.SCENARIO_SELECTION,
    STEPS.ASSESSMENT,
    STEPS.REVIEW,
  ];

  const currentStepIdx = STEP_ORDER.indexOf(step);

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <button
          type="button"
          className="navbar-brand navbar-home"
          onClick={onHome}
          title="Go to the start page"
        >
          <span className="brand-text">Expert Elicitation</span>
        </button>

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
          {autosaved && <span className="navbar-saved">Saved on this device</span>}
          {onOpenGuide && (
            <button className="navbar-guide-btn" onClick={onOpenGuide}>
              <BookOpen size={14} strokeWidth={2} />
              <span>About the study</span>
            </button>
          )}
          {expert?.name && (
            <>
              <span className="expert-avatar">{expert.name.charAt(0).toUpperCase()}</span>
              <span className="expert-name">{expert.name.split(" ")[0]}</span>
            </>
          )}
        </div>
      </div>

      {/* Progress bar for assessment step */}
      {/* {step === STEPS.ASSESSMENT && totalSteps > 0 && (
        <div className="navbar-progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      )} */}
    </nav>
  );
}
