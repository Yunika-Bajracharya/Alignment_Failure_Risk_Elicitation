import React from 'react';
import { Tally1, Tally2, Tally3, ChevronRight, Shield, Sparkles } from 'lucide-react';
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

export default function LandingPage({ onStart }) {
  return (
    <div className="landing2">
      <section className="l2-hero">
        <div className="l2-hero-backdrop" aria-hidden="true">
          <span className="l2-grid" />
        </div>
        <div className="l2-hero-inner">
          <div className="l2-hero-left">
            <p className="l2-eyebrow">Expert Elicitation · AI Safety</p>
            <h1 className="l2-title">
              How well does an alignment technique work across different failure modes?
            </h1>
            <p className="l2-subtitle">
              A structured elicitation tool for AI researchers and practitioners to
              quantify how alignment techniques affect the probability of specific
              failure modes.
            </p>
            <div className="l2-hero-actions">
              <button className="btn-primary btn-lg" onClick={onStart}>
                Begin Survey <ChevronRight size={16} strokeWidth={2.2} />
              </button>
              {/* <span className="l2-time-note">≈ {TOTAL_MIN} min for the full {failureModes.length} × {alignmentTechniques.length} set</span> */}
              <span className="l2-time-note">≈ 120 min (on average) for 12 assessments</span>

            </div>

            {ANONYMOUS && (
              <p className="l2-privacy-note">
                <Shield size={15} strokeWidth={1.8} />
                <span>
                  This survey is <strong>fully anonymous</strong> — no names or emails are collected.
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
            Start the Survey <ChevronRight size={16} strokeWidth={2.2} />
          </button>
        </div>
        <p className="l2-footer-note">AI Safety Elicitation Study · Expert Survey Tool</p>
      </section>
    </div>
  );
}
