import React from 'react';
import { Tally1, Tally2, Tally3, ChevronRight, Shield, Sparkles } from 'lucide-react';

const TECHNIQUES = [
  { short: 'RLHF', color: '#4f74cb' },
  { short: 'CAI', color: '#4ca2c0' },
  { short: 'Adv. Fine-Tuning', color: '#c96e74' },
  { short: 'AI Debate', color: '#9667c3' },
  { short: 'IDA', color: '#5fa479' },
  { short: 'RepE', color: '#bd884e' },
  { short: 'W2SG', color: '#4aa298' },
  { short: 'Mech. Interp.', color: '#866bc8' },
  { short: 'Const. Classifiers', color: '#b5a44f' },
];

const FM_CATEGORIES = [
  { label: 'Jailbreaking', color: '#b75e78' },
  { label: 'Sycophancy', color: '#c58949' },
  { label: 'Data Bias & Mode Collapse', color: '#5d97cc' },
  { label: 'Deceptive Alignment', color: '#8864a5' },
  { label: 'Sleeper Agents', color: '#6b9f70' },
];

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
              <span className="l2-time-note">≈ 45–90 min depending on scope</span>
            </div>
          </div>

          <div className="l2-hero-right">
            <div className="l2-scope-card">
              <div className="l2-scope-row">
                <span className="l2-scope-num">11</span>
                <span className="l2-scope-label">failure mode scenarios</span>
              </div>
              <div className="l2-scope-divider" />
              <div className="l2-scope-row">
                <span className="l2-scope-num">9</span>
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
