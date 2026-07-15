import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { getFMIcon, getTechIcon } from './Icons';

const CONFIDENCE_LEVELS = [
  { value: 1, label: 'Very Low', desc: 'I have very limited basis for this estimate', color: '#ef4444cb' },
  { value: 2, label: 'Low', desc: 'I have some basis but significant uncertainty', color: '#f97416c2' },
  { value: 3, label: 'Moderate', desc: 'I have a reasonable basis for this estimate', color: '#eab308' },
  { value: 4, label: 'High', desc: 'I have a strong basis and am fairly confident', color: '#22c55e' },
  { value: 5, label: 'Very High', desc: 'I am highly confident in this estimate', color: '#10b981' },
];

export default function AssessmentForm({
  failureMode,
  technique,
  formData,
  setFormData,
  onNext,
  onPrev,
  isFirst,
  isLast,
}) {
  const [errors, setErrors] = useState({});
  const [showHelp, setShowHelp] = useState(false);

  const update = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((e) => ({ ...e, [field]: null }));
  };

  const validate = () => {
    if (formData.notApplicable) return {};
    const e = {};
    const pe = parseFloat(formData.pointEstimate);
    const lb = parseFloat(formData.lowerBound);
    const ub = parseFloat(formData.upperBound);
    if (formData.pointEstimate === '' || isNaN(pe)) e.pointEstimate = 'Point estimate is required';
    else if (pe < -100 || pe > 100) e.pointEstimate = 'Must be between -100 and 100';
    if (formData.lowerBound === '' || isNaN(lb)) e.lowerBound = 'Lower bound is required';
    if (!Number.isFinite(lb)) {
    e.lowerBound = 'Lower bound must be a valid number';
}
    if (formData.upperBound === '' || isNaN(ub)) e.upperBound = 'Upper bound is required';
    if (formData.lowerBound !== '' && !isNaN(lb) && formData.pointEstimate !== '' && lb > pe)
          e.lowerBound = 'Lower bound must be ≤ point estimate';
    if (formData.upperBound !== '' && !isNaN(ub) && formData.pointEstimate !== '' && ub < pe)
      e.upperBound = 'Upper bound must be ≥ point estimate';
    if (formData.upperBound > 100) e.upperBound = 'Upper bound must be ≤ 100';
    if (formData.lowerBound < -100) e.lowerBound = 'Lower bound must be ≥ -100';
    if (!/^[-+]?\d*\.?\d+$/.test(formData.lowerBound)) {
      e.lowerBound = 'Lower bound must be a valid number';
    }
    if (!formData.confidence) e.confidence = 'Please select a confidence level';
    if (!formData.rationale.trim()) e.rationale = 'Please provide your reasoning';
    return e;
  };

  const handleNext = () => {
    const e = validate();
    if (Object.keys(e).length > 0) {
      setErrors(e);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    onNext();
  };

  const pe = parseFloat(formData.pointEstimate);
  const FMIcon = getFMIcon(failureMode.id);
  const TechIcon = getTechIcon(technique.id);

  return (
    <div className="assessment-form-card">
      <div className="af-header" style={{ '--fm-color': failureMode.color, '--tech-color': technique.color }}>
        <h3 className="af-header-question">
          How much does <em>{technique.shortName}</em> reduce the risk of <em>{failureMode.name}</em>?
        </h3>
        <p className="af-header-desc">
          Estimate the <strong>percentage reduction in attack/failure success rate</strong> relative
          to an SFT-only baseline. Negative values indicate the technique <em>increases</em> risk.
        </p>
        <button className="help-toggle" onClick={() => setShowHelp(!showHelp)}>
          {showHelp
            ? <><ChevronUp size={13} style={{ verticalAlign: 'middle' }} /> Hide guidance</>
            : <><ChevronDown size={13} style={{ verticalAlign: 'middle' }} /> Show estimation guidance</>}
        </button>
        {showHelp && (
          <div className="help-box">
            <p>
              <strong>What to estimate:</strong> The percentage point reduction in the fraction of
              adversarial attempts (or failure events) that succeed, compared to an SFT-only model
              under the same deployment conditions.
            </p>
            <p>
              <strong>Examples:</strong>
              <br />• 0 = no change from SFT baseline
              <br />• 50 = technique halves the success rate of attacks/failures
              <br />• 90 = technique reduces success rate by 90% (e.g. from 12% ASR to 1.2% ASR)
              <br />• -10 = technique increases success rate by 10% (i.e. makes things worse)
            </p>
            <p>
              <strong>Confidence interval:</strong> Provide your 90% credible interval.
              If you believe the true value has an 90% chance of falling between your bounds,
              those are your lower and upper bounds.
            </p>
          </div>
        )}
      </div>


      {(
        <>
          {/* Point Estimate */}
          <div className={`form-group ${errors.pointEstimate ? 'has-error' : ''}`}>
            <label className="form-label">
              Point Estimate (% reduction from SFT baseline)
              <span className="required">*</span>
            </label>
            <div className="estimate-input-row">
              <input
                type="range"
                min="-100"
                max="100"
                step="1"
                className="estimate-slider"
                value={formData.pointEstimate === '' ? 0 : formData.pointEstimate}
                onChange={(e) => update('pointEstimate', e.target.value)}
                style={{
                  '--slider-color': !isNaN(pe)
                    ? pe >= 0 ? '#22c55e' : '#ef4444'
                    : '#6366f1',
                }}
              />
              <div className="estimate-number-wrap">
                <input
                  type="number"
                  min="-100"
                  max="100"
                  step="0.5"
                  className={`estimate-number-input ${errors.pointEstimate ? 'error' : ''}`}
                  value={formData.pointEstimate}
                  onChange={(e) => update('pointEstimate', e.target.value)}
                  placeholder="0"
                />
                <span className="estimate-unit">%</span>
              </div>
            </div>
            <div className="slider-labels">
              <span>−100% (worse)</span>
              <span className="slider-center">0% (no change)</span>
              <span>+100% (eliminates risk)</span>
            </div>
            {!isNaN(pe) && formData.pointEstimate !== '' && (
              <div className={`estimate-interpretation ${pe >= 0 ? 'positive' : 'negative'}`}>
                {pe === 0 && '→ No change from SFT baseline'}
                {pe > 0 && pe < 50 && `→ Small reduction: technique reduces failure rate by ${pe}%`}
                {pe >= 50 && pe < 90 && `→ Moderate reduction: technique reduces failure rate by ${pe}%`}
                {pe >= 90 && `→ Large reduction: technique reduces failure rate by ${pe}%`}
                {pe < 0 && `→ Technique increases failure risk by ${Math.abs(pe)}%`}
              </div>
            )}
            {errors.pointEstimate && <span className="form-error">{errors.pointEstimate}</span>}
          </div>

          {/* Confidence Interval */}
          <div className={`form-group ${(errors.lowerBound || errors.upperBound) ? 'has-error' : ''}`}>
            <label className="form-label">
              Confidence Interval<span className="required">*</span>
            </label>
            <p className="form-hint">Your 90% credible interval: the range you believe contains the true value with ~90% probability.</p>
            <div className="ci-row">
              <div className={`ci-field ${errors.lowerBound ? 'has-error' : ''}`}>
                <label htmlFor="lb">Lower Bound</label>
                <div className="ci-input-wrap">
                  <input
                    id="lb"
                    type="text"
                    min="-100"
                    max="100"
                    step="0.5"
                    className={`form-input ${errors.lowerBound ? 'error' : ''}`}
                    placeholder="e.g. 10"
                    value={formData.lowerBound}
                    onChange={(e) => update('lowerBound', e.target.value)}
                  />
                  <span className="input-unit">%</span>
                </div>
                {errors.lowerBound && <span className="form-error">{errors.lowerBound}</span>}
              </div>
              <div className="ci-separator">
                <div className="ci-line" />
                <span>to</span>
                <div className="ci-line" />
              </div>
              <div className={`ci-field ${errors.upperBound ? 'has-error' : ''}`}>
                <label htmlFor="ub">Upper Bound</label>
                <div className="ci-input-wrap">
                  <input
                    id="ub"
                    type="number"
                    min="-100"
                    max="100"
                    step="0.5"
                    className={`form-input ${errors.upperBound ? 'error' : ''}`}
                    placeholder="e.g. 70"
                    value={formData.upperBound}
                    onChange={(e) => update('upperBound', e.target.value)}
                  />
                  <span className="input-unit">%</span>
                </div>
                {errors.upperBound && <span className="form-error">{errors.upperBound}</span>}
              </div>
            </div>
          </div>

          {/* Confidence Level */}
          <div className={`form-group ${errors.confidence ? 'has-error' : ''}`}>
            <label className="form-label">
              Confidence Level <span className="required">*</span>
            </label>
            <p className="form-hint">How confident are you in your estimate overall?</p>
            <div className="confidence-grid">
              {CONFIDENCE_LEVELS.map((cl) => (
                <label
                  key={cl.value}
                  className={`confidence-option ${formData.confidence === cl.value ? 'selected' : ''}`}
                  style={{ '--conf-color': cl.color }}
                >
                  <input
                    type="radio"
                    name="confidence"
                    value={cl.value}
                    checked={formData.confidence === cl.value}
                    onChange={() => update('confidence', cl.value)}
                  />
                  <span className="conf-value">{cl.value}</span>
                  <span className="conf-label">{cl.label}</span>
                  <span className="conf-desc">{cl.desc}</span>
                </label>
              ))}
            </div>
            {errors.confidence && <span className="form-error">{errors.confidence}</span>}
          </div>

          {/* Rationale */}
          <div className={`form-group ${errors.rationale ? 'has-error' : ''}`}>
            <label className="form-label" htmlFor="rationale">
              Reasoning & Rationale <span className="required">*</span>
            </label>
            <p className="form-hint">
              Explain your estimate. Which aspects of this technique do you think are most/least
              effective against this failure mode? What key uncertainties are you accounting for?
            </p>
            <textarea
              id="rationale"
              className={`form-textarea ${errors.rationale ? 'error' : ''}`}
              rows={5}
              placeholder=""
              value={formData.rationale}
              onChange={(e) => update('rationale', e.target.value)}
            />
            <div className="char-count">{formData.rationale.length} characters</div>
            {errors.rationale && <span className="form-error">{errors.rationale}</span>}
          </div>
        </>
      )}

      {/* Navigation */}
      <div className="form-actions spread">
        <button className="btn-ghost" onClick={onPrev}>
          ← {isFirst ? 'Back to Selection' : 'Previous'}
        </button>
        <button className="btn-primary" onClick={handleNext}>
          {isLast ? 'Review All Responses' : 'Save & Continue'}
          <span className="btn-arrow">{isLast ? ' →' : ' →'}</span>
        </button>
      </div>
    </div>
  );
}
