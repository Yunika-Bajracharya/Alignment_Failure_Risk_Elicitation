import React from 'react';
import { UserRound, Map, FileText, Download } from 'lucide-react';

const TECHNIQUES = [
  { short: 'RLHF', color: '#4f46e5' },
  { short: 'CAI', color: '#0891b2' },
  { short: 'Adv. Fine-Tuning', color: '#dc2626' },
  { short: 'AI Debate', color: '#7c3aed' },
  { short: 'IDA', color: '#059669' },
  { short: 'RepE', color: '#b45309' },
  { short: 'W2SG', color: '#0e7490' },
  { short: 'Mech. Interp.', color: '#9333ea' },
  { short: 'Const. Classifiers', color: '#15803d' },
];

const FM_CATEGORIES = [
  { label: 'Jailbreaking', color: '#dc2626' },
  { label: 'Sycophancy', color: '#d97706' },
  { label: 'Data Bias & Mode Collapse', color: '#2563eb' },
  { label: 'Deceptive Alignment', color: '#7c3aed' },
  { label: 'Sleeper Agents', color: '#b91c1c' },
];

export default function LandingPage({ onStart }) {
  return (
    <div className="landing2">
      {/* ── Hero ─────────────────────────────── */}
      <section className="l2-hero">
        <div className="l2-hero-inner">
          <div className="l2-hero-left">
            <p className="l2-eyebrow">Expert Elicitation · AI Safety</p>
            <h1 className="l2-title">
              How well does a alignment technique{' '}
              work across different failure modes?
            </h1>
            <p className="l2-subtitle">
              A structured elicitation tool for AI researchers and practitioners to
              quantify how alignment techniques affect the probability of specific
              failure modes.
            </p>
            <div className="l2-hero-actions">
              <button className="btn-primary btn-lg" onClick={onStart}>
                Begin Survey <span className="btn-arrow">→</span>
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

      {/* ── What you'll do ────────────────────── */}
      <section className="l2-section l2-steps-section">
        <div className="l2-container">
          <h2 className="l2-section-heading">Steps</h2>
          <div className="l2-steps-row">
            {[
              { icon: UserRound, text: 'Fill in your expert profile and select which scenarios to assess' },
              { icon: Map, text: 'Review deployment contexts  threat model, system capabilities, and setup' },
              { icon: FileText, text: 'Read technique documentation and provide estimates with CIs and reasoning' },
            ].map((s, i) => (
              <div key={i} className="l2-step">
                <span className="l2-step-n"><s.icon size={18} strokeWidth={1.8} /></span>
                <p className="l2-step-text">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Scope ─────────────────────────────── */}
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

      {/* ── Footer CTA ────────────────────────── */}
      <section className="l2-footer-cta">
        <div className="l2-container l2-footer-cta-inner">
          <button className="btn-primary" onClick={onStart}>
            Start the Survey <span className="btn-arrow">→</span>
          </button>
        </div>
        <p className="l2-footer-note">AI Safety Elicitation Study · Expert Survey Tool</p>
      </section>
    </div>
  );
}
