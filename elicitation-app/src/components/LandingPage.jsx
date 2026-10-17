import React from 'react';
import { Tally1, Tally2, Tally3, ChevronRight, Shield, Sparkles, BookOpen, Clock, Users, RefreshCw, BarChart3 } from 'lucide-react';
import { alignmentTechniques } from '../data/alignmentTechniques';
import { failureModes, failureModeCategories } from '../data/failureModes';
import { ANONYMOUS } from '../config';

// Everything below is derived from the active config (see src/config.js): the
// scope counts, the chips/dots, and the time estimate all follow whichever
// techniques / failure modes are currently loaded.
const TECHNIQUES = alignmentTechniques.map((t) => ({ short: t.shortName, color: t.color }));
const FM_CATEGORIES = failureModeCategories.map((c) => ({ label: c.label, color: c.color }));

// Time model: we budget ~5 min per (technique × failure-mode) assessment, so the
// full 2×2 set lands at ~20 min.
const PER_ASSESSMENT_MIN = 5;
const TOTAL_MIN = failureModes.length * alignmentTechniques.length * PER_ASSESSMENT_MIN;

const formatSavedAt = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};

export default function LandingPage({ onStart, onOpenGuide, draft, onStartOver }) {
  return (
    <div className="landing2">
      <section className="l2-hero">
        <div className="l2-hero-backdrop" aria-hidden="true">
          <span className="l2-grid" />
        </div>
        <div className="l2-hero-inner">
          <div className="l2-hero-left">
            <h1 className="l2-title">
              How well does an alignment technique work across different failure modes?
            </h1>
            <p className="l2-subtitle">
              A structured elicitation tool for AI researchers and practitioners to
              quantify how alignment techniques affect the probability of specific
              failure modes.
            </p>
            {draft && (
              <div className="l2-resume" role="status">
                <strong className="l2-resume-title">You have a saved response on this device</strong>
                <span className="l2-resume-meta">
                  Round {draft.round || '?'}, Track {draft.track || '?'}: {draft.answered} of{' '}
                  {draft.total || '?'} items answered
                  {draft.savedAt ? `, last saved ${formatSavedAt(draft.savedAt)}` : ''}.
                </span>
                <div className="l2-resume-actions">
                  <button className="btn-ghost btn-sm" onClick={onStartOver}>
                    Discard it and start a new response
                  </button>
                </div>
              </div>
            )}
            <div className="l2-hero-actions">
              <button className="btn-primary btn-lg" onClick={onStart}>
                {draft ? 'Continue where you left off' : 'Begin Survey'}{' '}
                <ChevronRight size={16} strokeWidth={2.2} />
              </button>
              {/* <span className="l2-time-note">≈ {TOTAL_MIN} min for the full {failureModes.length} × {alignmentTechniques.length} set</span> */}
              <button className="btn-ghost btn-lg l2-guide-btn" onClick={onOpenGuide}>
                <BookOpen size={16} strokeWidth={2} /> About the study
              </button>
              {/* <span className="l2-time-note">≈ 120 min (on average) for 12 assessments</span> */}

            </div>

            {ANONYMOUS && (
              <p className="l2-privacy-note">
                <Shield size={15} strokeWidth={1.8} />
                <span>
                  This survey is <strong>fully anonymous.</strong> No names or emails are associated with your responses.
                  Your responses are used only during this workshop to speed up aggregation, and are
                  deleted immediately afterwards.
                </span>
              </p>
            )}
          </div>

          <div className="l2-hero-right">
            <div className="l2-scope-card">
              <div className="l2-scope-row">
                <span className="l2-scope-num">{failureModes.length}</span>
                <span className="l2-scope-label">failure mode scenarios</span>
              </div>
              <div className="l2-scope-divider" />
              <div className="l2-scope-row">
                <span className="l2-scope-num">{alignmentTechniques.length}</span>
                <span className="l2-scope-label">alignment techniques</span>
              </div>
              <div className="l2-scope-divider" />
              <div className="l2-scope-row">
                <span className="l2-scope-num">∞</span>
                <span className="l2-scope-label">select &amp; assess</span>
              </div>
              <div className="l2-scope-tech-strip">
                {TECHNIQUES.map((t) => (
                  <span
                    key={t.short}
                    className="l2-tech-dot"
                    style={{ background: t.color }}
                    title={t.short}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="l2-section l2-involve-section">
        <div className="l2-container">
          <h2 className="l2-section-heading">The process</h2>
          <p className="l2-involve-lede">
            About four hours in total, most of it on your own before the workshop. You answer
            privately, discuss with a small group, then answer privately again.
          </p>
          <div className="l2-involve-row">
            {[
              { icon: Clock, when: 'Round 1', length: 'About 2 hours', text: 'On your own, before the workshop. 12 estimates, roughly 10 minutes each.' },
              { icon: Users, when: 'Discussion', length: '90 minutes', text: 'A facilitated session with about six experts on the six items in your track.' },
              { icon: RefreshCw, when: 'Round 2', length: 'After the discussion', text: 'Privately revise your estimates, or keep them if you were not persuaded.' },
              { icon: BarChart3, when: 'Results', length: 'After the workshop', text: 'We share a short summary of the final estimates.' },
            ].map((c) => (
              <div key={c.when} className="l2-involve-card">
                <c.icon size={17} strokeWidth={1.9} className="l2-involve-icon" />
                <span className="l2-involve-when">{c.when}</span>
                <strong className="l2-involve-length">{c.length}</strong>
                <span className="l2-involve-text">{c.text}</span>
              </div>
            ))}
          </div>
          <button className="l2-involve-link" onClick={onOpenGuide}>
            Read the full guide: goals, how your answers are used, and common questions
            <ChevronRight size={15} strokeWidth={2.2} />
          </button>
        </div>
      </section>

      <section className="l2-section l2-steps-section">
        <div className="l2-container">
            <h2 className="l2-section-heading">Steps during the Survey</h2>
          <div className="l2-steps-row">
            {[
              {
                icon: Tally1,
                title: 'Profile your expertise',
                text: 'Share your background and the areas where your judgment is strongest.',
              },
              {
                icon: Tally2,
                title: 'Review deployment context',
                text: 'Inspect the scenario, threat model, and system setup before estimating.',
              },
              {
                icon: Tally3,
                title: 'Provide estimates and rationale',
                text: 'Record point estimates, confidence intervals, and the reasoning behind them.',
              },
            ].map((s, i) => (
              <div key={i} className="l2-step">
                <span className="l2-step-icon"><s.icon size={18} strokeWidth={2} /></span>
                <strong className="l2-step-title">{s.title}</strong>
                <span className="l2-step-text">{s.text}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="l2-section l2-scope-section">
        <div className="l2-container l2-scope-cols">
          <div className="l2-scope-col">
            <h3 className="l2-col-heading">Failure Modes</h3>
            <div className="l2-tag-list">
              {FM_CATEGORIES.map((fm) => (
                <span key={fm.label} className="l2-tag" style={{ '--tag-color': fm.color }}>
                  {fm.label}
                </span>
              ))}
            </div>
          </div>
          <div className="l2-scope-col">
            <h3 className="l2-col-heading">Alignment Techniques</h3>
            <div className="l2-tag-list">
              {TECHNIQUES.map((t) => (
                <span key={t.short} className="l2-tag" style={{ '--tag-color': t.color }}>
                  {t.short}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="l2-footer-cta">
        <div className="l2-container l2-footer-cta-inner">
          <button className="btn-primary" onClick={onStart}>
            {draft ? 'Continue the survey' : 'Start the Survey'}{' '}
            <ChevronRight size={16} strokeWidth={2.2} />
          </button>
        </div>
        <p className="l2-footer-note">AI Safety Elicitation Study · Expert Survey Tool</p>
      </section>
    </div>
  );
}
