import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, User, Check } from 'lucide-react';

const CONFIDENCE_LABELS = { 1: 'Very Low', 2: 'Low', 3: 'Moderate', 4: 'High', 5: 'Very High' };
const CONFIDENCE_COLORS = { 1: '#ef4444', 2: '#f97316', 3: '#eab308', 4: '#22c55e', 5: '#10b981' };

export default function ReviewSubmit({ expert, selectedFMs, alignmentTechniques, assessments, onBack, onEdit, onSubmit }) {
  const [confirming, setConfirming] = useState(false);

  const totalPairs = selectedFMs.length * alignmentTechniques.length;
  const answeredPairs = selectedFMs.reduce((acc, fm) => {
    return acc + alignmentTechniques.filter((t) => assessments[fm.id]?.[t.id]).length;
  }, 0);
  const completion = Math.round((answeredPairs / totalPairs) * 100);

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="page-step-badge">Step 3 of 3 — Review</div>
        <h1>Review Your Responses</h1>
        <p className="page-subtitle">
          Check your estimates below before submitting. Click <strong>Edit</strong> on any row to
          revise it. You've completed {answeredPairs} of {totalPairs} assessments ({completion}%).
        </p>
      </div>

      {/* Completion bar */}
      <div className="review-completion">
        <div className="review-completion-label">
          {completion === 100
            ? <><CheckCircle2 size={14} style={{ verticalAlign: 'middle', color: '#166534' }} /> All assessments complete</>
            : <><AlertTriangle size={14} style={{ verticalAlign: 'middle', color: '#a16207' }} /> {totalPairs - answeredPairs} assessments incomplete</>}
        </div>
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{ width: `${completion}%`, background: completion === 100 ? '#22c55e' : '#f59e0b' }}
          />
        </div>
      </div>

      {/* Expert summary */}
      <div className="review-expert-card">
        <h3><User size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />Expert Profile</h3>
        <div className="review-expert-grid">
          <div><label>Name</label><span>{expert.name}</span></div>
          <div><label>Affiliation</label><span>{expert.affiliation || '—'}</span></div>
          <div><label>Role</label><span>{expert.role}</span></div>
          <div><label>Experience</label><span>{expert.yearsExperience} years</span></div>
        </div>
        {expert.expertiseAreas.length > 0 && (
          <div className="review-expertise-tags">
            {expert.expertiseAreas.map((a) => (
              <span key={a} className="expertise-tag">{a}</span>
            ))}
          </div>
        )}
      </div>

      {/* Results table by failure mode */}
      {selectedFMs.map((fm, fmIdx) => (
        <div key={fm.id} className="review-fm-section">
          <div className="review-fm-header" style={{ '--cat-color': fm.color }}>
            <span className="review-fm-icon">{fm.icon}</span>
            <div>
              <h3>{fm.name}</h3>
              <span className="review-fm-scenario">{fm.scenarioLabel}</span>
            </div>
          </div>
          <div className="review-table-wrap">
            <table className="review-table">
              <thead>
                <tr>
                  <th>Technique</th>
                  <th>Point Est.</th>
                  <th>Range</th>
                  <th>Confidence</th>
                  <th>Rationale</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {alignmentTechniques.map((tech, techIdx) => {
                  const a = assessments[fm.id]?.[tech.id];
                  return (
                    <tr key={tech.id} className={!a ? 'row-missing' : ''}>
                      <td>
                        <div className="review-tech-cell">
                          <span className="review-tech-dot" style={{ background: tech.color }} />
                          <span>{tech.shortName}</span>
                        </div>
                      </td>
                      <td>
                        {!a ? (
                          <span className="missing-badge">Missing</span>
                        ) : a.notApplicable ? (
                          <span className="na-badge">N/A</span>
                        ) : (
                          <span
                            className={`estimate-badge ${parseFloat(a.pointEstimate) >= 0 ? 'pos' : 'neg'}`}
                          >
                            {parseFloat(a.pointEstimate) >= 0 ? '+' : ''}{a.pointEstimate}%
                          </span>
                        )}
                      </td>
                      <td>
                        {a && !a.notApplicable && (a.lowerBound || a.upperBound) ? (
                          <span className="ci-badge">
                            {a.lowerBound || '?'}% – {a.upperBound || '?'}%
                          </span>
                        ) : '—'}
                      </td>
                      <td>
                        {a && !a.notApplicable && a.confidence ? (
                          <span
                            className="conf-badge"
                            style={{ background: CONFIDENCE_COLORS[a.confidence] + '22', color: CONFIDENCE_COLORS[a.confidence] }}
                          >
                            {CONFIDENCE_LABELS[a.confidence]}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="rationale-cell">
                        {a && !a.notApplicable ? (
                          <span className="rationale-preview">{a.rationale?.slice(0, 80)}…</span>
                        ) : a?.notApplicable ? (
                          <em className="text-muted">Marked not applicable</em>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td>
                        <button
                          className="btn-ghost btn-xs"
                          onClick={() => onEdit(fmIdx, techIdx)}
                        >
                          {a ? 'Edit' : 'Fill'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {/* Actions */}
      <div className="review-actions">
        <button className="btn-ghost" onClick={onBack}>
          ← Back to Assessment
        </button>
        <div className="review-submit-group">
          {!confirming ? (
            <button
              className="btn-primary"
              onClick={() => setConfirming(true)}
            >
              Submit & Export Responses
            </button>
          ) : (
            <div className="confirm-submit">
              <p>Ready to finalize? You'll be able to download your responses as JSON and CSV.</p>
              <div className="confirm-btns">
                <button className="btn-ghost" onClick={() => setConfirming(false)}>Cancel</button>
                <button className="btn-primary btn-success" onClick={onSubmit}>
                  <Check size={14} /> Confirm &amp; Export
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
