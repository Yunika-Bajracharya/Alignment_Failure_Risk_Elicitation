import React, { useState } from 'react';

const EXPERTISE_AREAS = [
  'RLHF / Preference Learning',
  'Constitutional AI / RLAIF',
  'Adversarial ML / Red-Teaming',
  'Mechanistic Interpretability',
  'Scalable Oversight',
  'Formal Verification',
  'Biosecurity / Dual-use AI',
  'AI Policy & Governance',
  'Fairness / Bias Mitigation',
  'Multi-agent Systems',
  'Deceptive Alignment Theory',
  'Empirical Alignment Research',
  'AI Risk Assessment',
  'Cognitive Science / HCI',
  'Other',
];

const ROLE_OPTIONS = [
  'Theoretical AI Safety Researcher',
  'Applied ML Researcher',
  'Applied AI Engineer',
  'AI Safety Policy / Governance',
  'Mechanistic Interpretability Researcher',
  'Adversarial Evaluation / Red-Teamer',
  'AI Safety Program Director',
  'Biosecurity / Dual-use Expert',
  'Cognitive Science / HCI Researcher',
  'Other',
];

const OTHER_EXPERTISE_LABEL = 'Other';

const parseOtherExpertiseAreas = (value) =>
  value
    .split(/[\n,;]/)
    .map((area) => area.trim())
    .filter(Boolean);

const normalizeExpertiseAreas = (expertiseAreas, otherExpertiseAreas) => {
  const fixedAreas = expertiseAreas.filter((area) => area !== OTHER_EXPERTISE_LABEL);
  const typedAreas = parseOtherExpertiseAreas(otherExpertiseAreas || '');
  const normalized = Array.from(new Set([...fixedAreas, ...typedAreas]));
  return normalized;
};

export default function ExpertProfile({ expert, setExpert, onNext }) {
  const [errors, setErrors] = useState({});

  const validate = () => {
    const e = {};
    if (!expert.name.trim()) e.name = 'Name is required';
    if (!expert.email.trim()) e.email = 'Email is required';
    if (!expert.affiliation.trim()) e.affiliation = 'Affiliation is required';
    if (!expert.role) e.role = 'Please select your role';
    if (expert.role === 'Other' && !expert.otherRole?.trim()) {
      e.otherRole = 'Please specify your role';
    }
    if (!expert.yearsExperience) e.yearsExperience = 'Please select your years of experience';
    const typedOtherAreas = parseOtherExpertiseAreas(expert.otherExpertiseAreas || '');
    const selectedAreas = expert.expertiseAreas.filter((area) => area !== OTHER_EXPERTISE_LABEL);
    if (selectedAreas.length === 0 && typedOtherAreas.length === 0) {
      e.expertiseAreas = 'Please select at least one expertise area';
    }
    if (expert.expertiseAreas.includes(OTHER_EXPERTISE_LABEL) && typedOtherAreas.length === 0) {
      e.otherExpertiseAreas = 'Please list at least one expertise area';
    }
    return e;
  };

  const handleNext = () => {
    const e = validate();
    if (Object.keys(e).length > 0) {
      setErrors(e);
      return;
    }
    setExpert((prev) => ({
      ...prev,
      expertiseAreas: normalizeExpertiseAreas(prev.expertiseAreas, prev.otherExpertiseAreas),
    }));
    onNext();
  };

  const toggleExpertise = (area) => {
    setExpert((prev) => ({
      ...prev,
      expertiseAreas: prev.expertiseAreas.includes(area)
        ? prev.expertiseAreas.filter((a) => a !== area)
        : [...prev.expertiseAreas, area],
      otherExpertiseAreas: area === OTHER_EXPERTISE_LABEL && prev.expertiseAreas.includes(area)
        ? ''
        : prev.otherExpertiseAreas,
    }));
    if (errors.expertiseAreas) setErrors((e) => ({ ...e, expertiseAreas: null }));
    if (errors.otherExpertiseAreas) setErrors((e) => ({ ...e, otherExpertiseAreas: null }));
  };

  const handleChange = (field) => (e) => {
    setExpert((prev) => ({ ...prev, [field]: e.target.value }));
    if (errors[field]) setErrors((err) => ({ ...err, [field]: null }));
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-step-badge">Step 1 of 3</div>
        <h1>Your Expert Profile</h1>
        <p className="page-subtitle">
          This information helps contextualize your estimates and will be included with your
          exported responses.
        </p>
      </div>

      <div className="form-card">
        <div className="form-section">
          <h3 className="form-section-title">Personal Information</h3>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="name">
                Full Name <span className="required">*</span>
              </label>
              <input
                id="name"
                type="text"
                className={`form-input ${errors.name ? 'error' : ''}`}
                placeholder="Dr. Jane Smith"
                value={expert.name}
                onChange={handleChange('name')}
              />
              {errors.name && <span className="form-error">{errors.name}</span>}
            </div>
            <div className="form-group">
              <label htmlFor="email">Email Address<span className="required">*</span></label>
              <input
                id="email"
                type="email"
                className={`form-input ${errors.email ? 'error' : ''}`}
                placeholder="jane@institution.edu"
                value={expert.email}
                onChange={handleChange('email')}
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="affiliation">Affiliation / Organization<span className="required">*</span></label>
              <input
                id="affiliation"
                type="text"
                className={`form-input ${errors.affiliation ? 'error' : ''}`}
                placeholder="University, Lab, or Company"
                value={expert.affiliation}
                onChange={handleChange('affiliation')}
              />
            </div>
            <div className="form-group">
              <label htmlFor="role">
                Primary Role <span className="required">*</span>
              </label>
              <select
                id="role"
                className={`form-select ${errors.role ? 'error' : ''}`}
                value={expert.role}
                onChange={(e) => {
                  const nextRole = e.target.value;
                  setExpert((prev) => ({
                    ...prev,
                    role: nextRole,
                    otherRole: nextRole === 'Other' ? prev.otherRole : '',
                  }));
                  if (errors.role || errors.otherRole) {
                    setErrors((err) => ({ ...err, role: null, otherRole: null }));
                  }
                }}
              >
                <option value="">Select your role…</option>
                {ROLE_OPTIONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
              {errors.role && <span className="form-error">{errors.role}</span>}
            </div>
          </div>
          {expert.role === 'Other' && (
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="otherRole">
                  Please specify your role <span className="required">*</span>
                </label>
                <input
                  id="otherRole"
                  type="text"
                  className={`form-input ${errors.otherRole ? 'error' : ''}`}
                  placeholder="Your primary role"
                  value={expert.otherRole || ''}
                  onChange={handleChange('otherRole')}
                />
                {errors.otherRole && <span className="form-error">{errors.otherRole}</span>}
              </div>
            </div>
          )}
          <div className="form-group" style={{ maxWidth: '280px' }}>
            <label htmlFor="years">
              Years of Experience in AI Safety / ML <span className="required">*</span>
            </label>
            <select
              id="years"
              className={`form-select ${errors.yearsExperience ? 'error' : ''}`}
              value={expert.yearsExperience}
              onChange={handleChange('yearsExperience')}
            >
              <option value="">Select…</option>
              <option value="<1">Less than 1 year</option>
              <option value="1-2">1–2 years</option>
              <option value="3-5">3–5 years</option>
              <option value="6-9">6–9 years</option>
              <option value="10+">10+ years</option>
            </select>
            {errors.yearsExperience && (
              <span className="form-error">{errors.yearsExperience}</span>
            )}
          </div>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">
            Expertise Areas <span className="required">*</span>
          </h3>
          <p className="form-hint">Select all that apply to your primary research or professional focus.</p>
          {errors.expertiseAreas && (
            <span className="form-error block-error">{errors.expertiseAreas}</span>
          )}
          <div className="checkbox-grid">
            {EXPERTISE_AREAS.map((area) => (
              <label key={area} className={`checkbox-label ${expert.expertiseAreas.includes(area) ? 'checked' : ''}`}>
                <input
                  type="checkbox"
                  checked={expert.expertiseAreas.includes(area)}
                  onChange={() => toggleExpertise(area)}
                />
                <span className="checkbox-custom" />
                {area}
              </label>
            ))}
          </div>
            {expert.expertiseAreas.includes(OTHER_EXPERTISE_LABEL) && (
              <div className="form-group" style={{ marginTop: '18px' }}>
                <label htmlFor="otherExpertiseAreas">
                  Other expertise areas <span className="required">*</span>
                </label>
                <textarea
                  id="otherExpertiseAreas"
                  className={`form-textarea ${errors.otherExpertiseAreas ? 'error' : ''}`}
                  placeholder="Enter one or more areas, separated by commas or new lines"
                  value={expert.otherExpertiseAreas || ''}
                  onChange={handleChange('otherExpertiseAreas')}
                  rows={4}
                />
                {errors.otherExpertiseAreas && (
                  <span className="form-error">{errors.otherExpertiseAreas}</span>
                )}
              </div>
            )}
        </div>

        <div className="form-actions">
          <button className="btn-primary" onClick={handleNext}>
            Continue to Scenario Selection
            <span className="btn-arrow">→</span>
          </button>
        </div>
      </div>
    </div>
  );
}
