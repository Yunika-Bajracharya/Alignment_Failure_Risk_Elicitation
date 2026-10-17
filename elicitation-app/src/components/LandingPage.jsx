import React from 'react';
import { ArrowRight, ArrowUpRight } from 'lucide-react';
import { alignmentTechniques } from '../data/alignmentTechniques';
import { failureModes, failureModeCategories } from '../data/failureModes';
import { ANONYMOUS, INTEREST_FORM_URL } from '../config';

// Everything below is derived from the active config (see src/config.js): the
// item count and the scope lists follow whichever techniques / failure modes
// are currently loaded.

// Items per expert = the shared core (jailbreaking, sycophancy) + one track.
// Both tracks have the same number of techniques, so either one gives the count.
const techCount = (fmId) =>
  failureModeCategories.find((c) => c.id === fmId)?.alignmentTechniques.length || 0;
const ITEMS_PER_EXPERT =
  techCount('jailbreaking') + techCount('sycophancy') + techCount('sleeper_agents_backdoor');

const FACTS = [
  { value: ITEMS_PER_EXPERT, label: 'estimates per expert' },
  { value: '2', label: 'rounds, with a discussion between' },
  ...(ANONYMOUS ? [{ value: 'Anonymous', label: 'no names or emails linked to your answers' }] : []),
];

const PROCESS = [
  { when: 'Round 1', length: 'About 2 hours', text: 'On your own, before the workshop. 12 estimates, roughly 10 minutes each.' },
  { when: 'Discussion', length: '90 minutes', text: 'A facilitated session with about six experts on the six items in your track.' },
  { when: 'Round 2', length: 'After the discussion', text: 'Privately revise your estimates, or keep them if you were not persuaded.' },
  { when: 'Results', length: 'After the workshop', text: 'We share a short summary of the final estimates.' },
];

const SURVEY_STEPS = [
  { title: 'Profile your expertise', text: 'Share your background and the areas where your judgment is strongest.' },
  { title: 'Review deployment context', text: 'Inspect the scenario, threat model, and system setup before estimating.' },
  { title: 'Provide estimates and rationale', text: 'Record point estimates, confidence intervals, and the reasoning behind them.' },
];

const formatSavedAt = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
};

export default function LandingPage({ onStart, onOpenGuide, draft, onStartOver }) {
  return (
    <div className="lp">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <header className="lp-hero lp-wrap">
        <p className="lp-kicker">Expert elicitation study</p>
        <h1 className="lp-title">
          How well does an alignment technique work across different failure modes?
        </h1>
        <p className="lp-lede">
          A structured elicitation tool for AI researchers and practitioners to quantify how
          alignment techniques affect the probability of specific failure modes.
        </p>

        {draft && (
          <div className="lp-resume" role="status">
            <div>
              <strong>You have a saved response on this device.</strong>{' '}
              <span className="lp-muted">
                Round {draft.round || '?'}, Track {draft.track || '?'}: {draft.answered} of{' '}
                {draft.total || '?'} items answered
                {draft.savedAt ? `, last saved ${formatSavedAt(draft.savedAt)}` : ''}.
              </span>
            </div>
            <button className="lp-textbtn" onClick={onStartOver}>
              Discard and start over
            </button>
          </div>
        )}

        <div className="lp-actions">
          <button className="lp-btn" onClick={onStart}>
            {draft ? 'Continue where you left off' : 'Begin survey'}
            <ArrowRight size={16} strokeWidth={2} />
          </button>
          <button className="lp-textbtn lp-textbtn-lg" onClick={onOpenGuide}>
            About the study <ArrowRight size={15} strokeWidth={2} />
          </button>
        </div>

        {INTEREST_FORM_URL && (
          <p className="lp-interest">
            If you'd like to take part and receive the results,{' '}
            <a href={INTEREST_FORM_URL} target="_blank" rel="noreferrer">
              register your interest <ArrowUpRight size={14} strokeWidth={2} />
            </a>
          </p>
        )}

        <dl className="lp-facts">
          {FACTS.map((f) => (
            <div key={f.label} className="lp-fact">
              <dt>{f.value}</dt>
              <dd>{f.label}</dd>
            </div>
          ))}
        </dl>
      </header>

      {/* ── The process ──────────────────────────────────────────────────── */}
      <section className="lp-section lp-wrap">
        <div className="lp-section-head">
          <h2>The process</h2>
          <p>
            You answer privately, discuss with a small group, then answer privately again.
          </p>
        </div>
        <ol className="lp-list">
          {PROCESS.map((p) => (
            <li key={p.when} className="lp-row">
              <span className="lp-row-label">{p.when}</span>
              <strong className="lp-row-title">{p.length}</strong>
              <span className="lp-row-text">{p.text}</span>
            </li>
          ))}
        </ol>
        <button className="lp-textbtn" onClick={onOpenGuide}>
          Read the full guide <ArrowRight size={15} strokeWidth={2} />
        </button>
      </section>


      {/* ── What the study covers ────────────────────────────────────────── */}
      <section className="lp-cover lp-wrap" aria-label="What the study covers">
        <div className="lp-cover-col">
          <h3 className="lp-cover-label">
            Failure modes <span>{failureModeCategories.length}</span>
          </h3>
          <ul className="lp-chips">
            {failureModeCategories.map((fm) => (
              <li key={fm.id} className="l2-tag" style={{ '--tag-color': fm.color }}>{fm.label}</li>
            ))}
          </ul>
        </div>
        <div className="lp-cover-col">
          <h3 className="lp-cover-label">
            Alignment techniques <span>{alignmentTechniques.length}</span>
          </h3>
          <ul className="lp-chips">
            {alignmentTechniques.map((t) => (
              <li key={t.id} className="l2-tag" style={{ '--tag-color': t.color }}>{t.shortName}</li>
            ))}
          </ul>
        </div>
      </section>
      

      {/* ── Closing call to action ───────────────────────────────────────── */}
      <footer className="lp-footer lp-wrap">
        <h2>{draft ? 'Pick up where you left off.' : 'Begin the elicitation.'}</h2>
        <p className="lp-muted"></p>
        <button className="lp-btn" onClick={onStart}>
          {draft ? 'Continue the survey' : 'Begin survey'}
          <ArrowRight size={16} strokeWidth={2} />
        </button>
        <p className="lp-footnote">
          AI Safety Elicitation Study · {failureModes.length} failure modes ·{' '}
          {alignmentTechniques.length} techniques
        </p>
      </footer>
    </div>
  );
}
