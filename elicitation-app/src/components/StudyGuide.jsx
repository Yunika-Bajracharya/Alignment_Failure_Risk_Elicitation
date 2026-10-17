import React, { useEffect, useRef, useState } from 'react';
import { X, Clock, Users, RefreshCw, BarChart3, ExternalLink, ChevronRight } from 'lucide-react';
import { alignmentTechniques } from '../data/alignmentTechniques';
import { failureModes, failureModeCategories } from '../data/failureModes';
import { ANONYMOUS, CONTACT_EMAIL, INTEREST_FORM_URL } from '../config';

// Everything the guide says about items (which failure modes, which techniques,
// how many) is derived from the same data the survey uses, so it stays in sync
// if the study design changes.
const CORE_FM_IDS = ['jailbreaking', 'sycophancy'];
const TRACKS = [
  { id: 'A', fmId: 'sleeper_agents_backdoor' },
  { id: 'B', fmId: 'deceptive_alignment' },
];

const techById = Object.fromEntries(alignmentTechniques.map((t) => [t.id, t]));
const fmById = Object.fromEntries(failureModes.map((fm) => [fm.id, fm]));

const techIdsFor = (fmId) =>
  failureModeCategories.find((c) => c.id === fmId)?.alignmentTechniques || [];

const techNamesFor = (fmId) =>
  techIdsFor(fmId).map((id) => techById[id]?.shortName || id);

const CORE_BLOCKS = CORE_FM_IDS.map((fmId) => ({
  fm: fmById[fmId],
  techniques: techNamesFor(fmId),
}));

const TRACK_BLOCKS = TRACKS.map((t) => ({
  ...t,
  fm: fmById[t.fmId],
  techniques: techNamesFor(t.fmId),
}));

const CORE_COUNT = CORE_BLOCKS.reduce((n, b) => n + b.techniques.length, 0);
const TRACK_COUNT = TRACK_BLOCKS[0]?.techniques.length || 0;
const TOTAL_ITEMS = CORE_COUNT + TRACK_COUNT;

const papersOf = (item) => (item?.paper ? [item.paper] : item?.papers || []);
const READING_FMS = [...CORE_FM_IDS, ...TRACKS.map((t) => t.fmId)]
  .map((id) => fmById[id])
  .filter(Boolean);
const READING_TECHS = Array.from(
  new Set([...CORE_FM_IDS, ...TRACKS.map((t) => t.fmId)].flatMap(techIdsFor))
)
  .map((id) => techById[id])
  .filter(Boolean);

const SECTIONS = [
  { id: 'why', label: 'Why this study' },
  { id: 'time', label: 'Time commitment' },
  { id: 'steps', label: 'Step by step' },
  { id: 'items', label: 'What you will estimate' },
  { id: 'answer', label: 'How to answer' },
  // { id: 'method', label: 'The methodology' },
  // { id: 'reuse', label: 'Beyond this study' },
  { id: 'reading', label: 'Reading list' },
  { id: 'privacy', label: 'Your data' },
  { id: 'faq', label: 'Common questions' },
];

const COMMITMENT = [
  {
    icon: Clock,
    when: 'Round 1 · independently',
    length: '~ 2 hrs, or more depending on familiarity with material',
    text: `Before the workshop. Read the background material and estimate ${TOTAL_ITEMS} items, roughly 10 minutes each.`,
  },
  {
    icon: Users,
    when: 'Discussion · with your group',
    length: '90 minutes',
    text: `A facilitated session with about six experts, focused on the ${TRACK_COUNT} items in your track.`,
  },
  {
    icon: RefreshCw,
    when: 'Round 2 · independently',
    length: 'After the discussion',
    text: 'Privately revise your estimates, or keep them if you were not persuaded.',
  },
  {
    icon: BarChart3,
    when: 'Results · from us',
    length: 'After the workshop',
    text: 'A short summary of the final estimates.',
  },
];

// Inline citation: the author/year text links straight to the source.
function Cite({ href, children }) {
  return (
    <a className="guide-cite" href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}

function Email() {
  return <a className="guide-cite" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>;
}

function PaperLink({ paper }) {
  return (
    <a className="guide-paper" href={paper.url} target="_blank" rel="noreferrer">
      <span className="guide-paper-title">{paper.title}</span>
      <span className="guide-paper-meta">
        {paper.authors}, {paper.year} <ExternalLink size={12} strokeWidth={2} />
      </span>
    </a>
  );
}

export default function StudyGuide({ onClose, onStart }) {
  const closeRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  // Reading progress (0 to 1) and the section currently being read.
  const [progress, setProgress] = useState(0);
  const [activeId, setActiveId] = useState(SECTIONS[0].id);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return undefined;
    let frame = 0;
    const update = () => {
      frame = 0;
      const max = el.scrollHeight - el.clientHeight;
      setProgress(max > 0 ? Math.min(1, el.scrollTop / max) : 0);
      // The active topic is the last section whose top has passed just below the top bar.
      const line = el.scrollTop + 120;
      let current = SECTIONS[0].id;
      for (const s of SECTIONS) {
        const section = document.getElementById(`guide-${s.id}`);
        if (section && section.offsetTop <= line) current = s.id;
      }
      // Short sections at the end never reach the line, so the bottom selects the last one.
      if (max > 0 && el.scrollTop >= max - 2) current = SECTIONS[SECTIONS.length - 1].id;
      setActiveId(current);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    el.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      el.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      cancelAnimationFrame(frame);
    };
  }, []);

  const jumpTo = (id) => (e) => {
    e.preventDefault();
    const el = document.getElementById(`guide-${id}`);
    if (el && scrollRef.current) {
      scrollRef.current.scrollTo({ top: el.offsetTop - 84, behavior: 'smooth' });
    }
  };

  return (
    <div
      className="guide-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="guide-title"
      ref={scrollRef}
    >
      <header className="guide-topbar">
        <div className="guide-topbar-inner">
          <span className="guide-topbar-title">About the study</span>
          <button ref={closeRef} className="btn-ghost btn-sm guide-close" onClick={onClose}>
            <X size={15} strokeWidth={2} /> Close
          </button>
        </div>
        <div
          className="guide-progress"
          role="progressbar"
          aria-label="Reading progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
        >
          <span style={{ transform: `scaleX(${progress})` }} />
        </div>
      </header>

      <div className="guide-layout">
        <nav className="guide-toc" aria-label="Sections">
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#guide-${s.id}`}
              onClick={jumpTo(s.id)}
              className={activeId === s.id ? 'active' : undefined}
              aria-current={activeId === s.id ? 'true' : undefined}
            >
              {s.label}
            </a>
          ))}
        </nav>

        <article className="guide-body">
          <div className="guide-intro">
            <h1 id="guide-title">A guide for participating experts</h1>
            <p className="guide-lede">
              This guide covers what we want to learn,
              what we'll ask of you, and what happens to your answers. If anything is unclear, email us at{' '}
              <Email />.
            </p>
          </div>

          {/* ---------------------------------------------------------- WHY */}
          <section id="guide-why" className="guide-section">
            <h2>Why this study</h2>
            <p>
              We want to quantify:{' '}
              <strong>how much does a given alignment technique reduce a given failure
              mode?</strong>
            </p>
            <p>
              AI systems that are misused or aren't well aligned with what their developers and users intend can
              cause real harm, and some of these failures already occur in deployed models.
              In jailbreaking, adversarial prompts get around safety training (
              <Cite href="https://arxiv.org/abs/2307.02483">Wei et al., 2023</Cite>;{' '}
              <Cite href="https://arxiv.org/abs/2307.15043">Zou et al., 2023</Cite>). In
              sycophancy, models tell users what they want to hear instead of what is accurate (
              <Cite href="https://arxiv.org/abs/2310.13548">Sharma et al., 2023</Cite>;{' '}
              <Cite href="https://openai.com/index/sycophancy-in-gpt-4o/">OpenAI, 2025</Cite>).
              Defenses against these failures can be
              measured. Constitutional Classifiers, for example, cut jailbreak success from about
              86% to under 5% (
              <Cite href="https://arxiv.org/abs/2501.18837">Sharma et al., 2025</Cite>).
            </p>
            <p>
              Other failures are expected in more capable systems and can’t yet be induced easily.
              In July 2026, OpenAI
              models under cyber-capability evaluation broke out of their sandbox and compromised
              Hugging Face's production servers, an episode OpenAI itself called a warning shot
              for loss-of-control incidents (
              <Cite href="https://openai.com/index/hugging-face-model-evaluation-security-incident/">
                OpenAI and Hugging Face, 2026
              </Cite>
              ;{' '}
              <Cite href="https://openai.com/index/hugging-face-incident-and-the-road-ahead/">
                OpenAI, 2026
              </Cite>
              ). Systems like these may also fail in ways we haven't yet seen in production: a
              backdoor that survives safety training (
              <Cite href="https://arxiv.org/abs/2401.05566">sleeper agents</Cite>), or a model
              that behaves well only while it knows it is being evaluated (
              <Cite href="https://arxiv.org/abs/1906.01820">deceptive alignment</Cite>;{' '}
              <Cite href="https://arxiv.org/abs/2412.14093">Greenblatt et al., 2024</Cite>).
              Defending against them may take techniques that are promising but understudied,
              such as AI debate (
              <Cite href="https://arxiv.org/abs/1805.00899">Irving et al., 2018</Cite>;{' '}
              <Cite href="https://arxiv.org/abs/2402.06782">Khan et al., 2024</Cite>) or circuit
              breakers (<Cite href="https://arxiv.org/abs/2406.04313">Zou et al., 2024</Cite>).
            </p>
            <p>
              Deciding which techniques to develop needs an estimate of how much each one reduces
              each failure. For most pairs, though, there is no experiment to look at. Only one of
              the four cases below can be tested directly:
            </p>
            <div className="guide-table-wrap">
              <table className="guide-table guide-quadrant">
                <thead>
                  <tr>
                    <th></th>
                    <th>Failure exists today</th>
                    <th>Failure expected in more advanced AI</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th scope="row">Established technique</th>
                    <td>
                      <strong>Testable</strong>
                      <span>e.g. jailbreaking × Constitutional Classifiers</span>
                    </td>
                    <td>
                      <strong>No experiment possible</strong>
                      <span>The failure can't be induced. e.g. deceptive alignment × RLHF</span>
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">Emerging technique</th>
                    <td>
                      <strong>Hard to test</strong>
                      <span>No production-scale version exists. e.g. sycophancy × AI debate</span>
                    </td>
                    <td>
                      <strong>Doubly unknown</strong>
                      <span>e.g. sleeper agents × AI debate</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p>
              <Cite href="https://arxiv.org/abs/2510.11235">Dung and Mai (2025)</Cite> mapped seven alignment strategies against seven
              failure modes but their judgments are qualitative and yes-or-no, and were reached by
              argument rather than through a structured process. That means they can't be compared
              across cells, carry no uncertainty, and can't be combined across experts.
            </p>
            <p>
              Other safety fields facing rare or unprecedented failures, such as nuclear power risk assessment (
              <Cite href="https://www.nrc.gov/reading-rm/doc-collections/nuregs/staff/sr1150/">
                US NRC, 1990
              </Cite>
              ) and volcanic hazard forecasting (
              <Cite href="https://doi.org/10.1038/463294a">Aspinall, 2010</Cite>) use{' '}
              <em>structured expert elicitation</em> (
              <Cite href="https://doi.org/10.1111/2041-210X.12857">Hemming et al., 2018</Cite>). In AI safety,
              similar work has so far focused on misuse. For example,{' '}
              <Cite href="https://arxiv.org/abs/2512.08844">Murray et al. (2025)</Cite> used
              structured elicitation to turn a model's cyber-offense benchmark scores into
              estimates of the uplift it gives attackers. We apply it to the question of how effective an alignment technique is across a given failure mode.
            </p>
            <p>Your estimates will help us to:</p>
            <ul>
              <li>compare techniques against each other on one common scale;</li>
              <li>see where experts broadly agree and where they genuinely don't;</li>
              <li>
                give researchers, funders and policymakers a clearer, more honest picture of which
                safeguards are worth prioritising, uncertainty included.
              </li>
            </ul>
            <br/>
            <p>
              We ran the protocol with LLM-simulated experts to debug the
              questions. That pilot only tells us whether the instrument works. Your answers are
              the real data, and we will also compare them with the simulated panel to learn
              whether simulated panels are any use as a stand-in for human ones.
            </p>
          </section>

          {/* --------------------------------------------------------- TIME */}
          <section id="guide-time" className="guide-section">
            <h2>Time commitment</h2>
            <div>
              {COMMITMENT.map((c) => (
                <div key={c.when} className="guide-commit">
                  <c.icon size={18} strokeWidth={1.9} className="guide-commit-icon" />
                  <span className="guide-commit-when">{c.when}</span>
                  <strong className="guide-commit-length">{c.length}</strong>
                  <span className="guide-commit-text">{c.text}</span>
                </div>
              ))}
            </div>
          </section>

          {/* -------------------------------------------------------- STEPS */}
          <section id="guide-steps" className="guide-section">
            <h2>The steps</h2>
            <p>
              The study follows the <strong>IDEA protocol</strong>: Investigate, Discuss,
              Estimate, Aggregate. You answer on your own, discuss with a small group, then answer on your own again.
            </p>

            <h3>Round 1: Investigate and estimate (on your own)</h3>
            <p>
              The organisers will tell you your <strong>track</strong> (A or B) and, for the
              workshop, your <strong>group number</strong>. 
            </p>
            <ol className="guide-steps">
              <li>
                <strong>Open the survey</strong> and choose “First Round” and your track.
              </li>
              <li>
                <strong>Write down your participant ID.</strong> The app shows a short random
                code. You will need it in round 2 so we can link your two sets of answers. It
                doesn't identify you, which also means we can't look it up for you if it gets
                lost.
              </li>
              <li>
                <strong>Tell us a little about your background:</strong> your sector and your
                primary role. That's all.
              </li>
              <li>
                <strong>Read the deployment scenario.</strong> Before each block of items you'll
                see the setting, the threat model and what counts as the failure succeeding. It's
                worth a few minutes, because every estimate in that block refers to this exact
                setting.
              </li>
              <li>
                <strong>Estimate each item.</strong> The technique's overview and reference
                paper are on the left and the questions on the right.
              </li>
              <li>
                <strong>Review and submit.</strong> The review page lists all your answers, and
                you can jump back to change any of them before you submit.
              </li>
            </ol>
            <div className="guide-callout">
              <strong>You don't have to finish in one sitting.</strong> See "Saving your progress" below.
              {/* We still recommend jotting down your numbers and a line */}
              {/* of reasoning for each item, because round 2 starts from an empty form. */}
            </div>

            <h3>Discussion (90 minutes with your group)</h3>
            <p>
              Each group has about six experts and discusses the {TRACK_COUNT} items in their
              track. Before the session you'll see, for each of those items, the group's
              average, how spread out the estimates were, and anonymised reasoning from the
              lowest, a typical and the highest estimate. No names are attached to any number.
            </p>
            <div className="guide-table-wrap">
              <table className="guide-table">
                <thead>
                  <tr>
                    <th>Part</th>
                    <th>Time</th>
                    <th>What happens</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Introductions</td>
                    <td className="num">12 min</td>
                    <td>Two minutes each to say who you are and where your view comes from.</td>
                  </tr>
                  <tr>
                    <td>Technique discussion</td>
                    <td className="num">72 min</td>
                    <td>
                      The {TRACK_COUNT} track techniques, one at a time, with about two minutes per
                      person per technique.
                    </td>
                  </tr>
                  <tr>
                    <td>Wrap-up</td>
                    <td className="num">5 min</td>
                    <td>A short summary from the facilitator and instructions for round 2.</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <h3>Round 2: estimate again (after the discussion, on your own)</h3>
            <p>
              Open the survey again and choose “Second Round”. Then enter your track, group ID and the
              participant ID you wrote down in round 1. For each item, revise your estimate or restate it. Changing your mind because you heard a good argument and keeping your number because you weren't persuaded are equally valid. The
              discussion only covers your track's items, so you won't need to revise your answers for the {CORE_COUNT} core items.
            </p>

            <h3>Results (our part)</h3>
            <p>
              We combine everyone's answers and send you a short summary of the final estimates.
            </p>
          </section>

          {/* -------------------------------------------------------- ITEMS */}
          <section id="guide-items" className="guide-section">
            <h2>What you will estimate</h2>
            <p>Every item asks the same question about one technique and one failure mode:</p>
            <blockquote className="guide-question">
              By how much does this technique, applied on top of SFT instruction-tuning, reduce
              the success rate of this failure mode in the given scenario, compared with a model
              that only had SFT?
            </blockquote>
            <p>
              The <strong>SFT baseline</strong> is a model trained on human-written
              demonstrations to follow instructions, with no other alignment technique applied.
              Using the same baseline everywhere is what makes the items comparable.
            </p>

            <h3>Your {TOTAL_ITEMS} items</h3>
            <p>
              Everyone answers the same {CORE_COUNT} <strong>core items</strong>. You also answer
              the {TRACK_COUNT} items of your <strong>track</strong>.
            </p>
            <div className="guide-items-grid">
              <div className="guide-items-col">
                <span className="guide-items-tag">Core · everyone</span>
                {CORE_BLOCKS.map((b) => (
                  <div key={b.fm?.id} className="guide-items-block">
                    <strong style={{ color: b.fm?.color }}>{b.fm?.name}</strong>
                    <span>{b.techniques.join(', ')}</span>
                  </div>
                ))}
              </div>
              {TRACK_BLOCKS.map((b) => (
                <div key={b.id} className="guide-items-col">
                  <span className="guide-items-tag">Track {b.id} only</span>
                  <div className="guide-items-block">
                    <strong style={{ color: b.fm?.color }}>{b.fm?.name}</strong>
                    <span>{b.techniques.join(', ')}</span>
                  </div>
                </div>
              ))}
            </div>

            <h3>Why these failure modes</h3>
            <p>
              Jailbreaking and sycophancy have published measurements and already happen in deployed models, so they act as calibration: we can check expert judgment against existing evidence. Sleeper agents and deceptive alignment are expected in more capable systems, which is where measurement is difficult and expert judgment matters most.
            </p>

            <h3>Why everyone answers the core</h3>
            <p>
              Some people consistently estimate higher or lower than the rest of a panel.
              Because everyone answers the core items, we can see each person's tendency relative
              to the group, which puts Track A and Track B answers on a comparable footing.
              RLHF appears in every block for the same reason. We report this offset as a
              diagnostic only. We do not use it to change anyone's numbers.
            </p>

            <h3>The deployment scenario</h3>
            <p>
              Each failure mode comes with a fixed scenario. It specifies who deploys the model, what
              it is used for, how it is monitored and what counts as the failure succeeding.
              This means when two experts disagree, they disagree about
              the technique rather than about different imagined deployments. Please answer for the
              scenario as written. If you think it can be improved, please write to us at <Email />.
            </p>
          </section>

          {/* ------------------------------------------------------- ANSWER */}
          <section id="guide-answer" className="guide-section">
            <h2>How to answer each item</h2>
            <p>Each item has four parts.</p>
            <dl className="guide-dl">
              <dt>1. Best estimate</dt>
              <dd>
                The percentage reduction in the failure's success rate compared with the SFT
                baseline, anywhere from −100 to 100.
                <ul>
                  <li><strong>0</strong> means no change from SFT.</li>
                  <li><strong>50</strong> means the technique halves the success rate.</li>
                  <li>
                    <strong>90</strong> means a 90% reduction, for example from a 12% attack
                    success rate down to 1.2%.
                  </li>
                  <li>
                    <strong>Negative values</strong> mean the technique makes the failure more
                    likely.
                  </li>
                </ul>
              </dd>
              <dt>2. A 90% interval</dt>
              <dd>
                A lower and upper bound you'd be surprised to see the true value fall outside of. If you’re unsure, a wide interval is much more useful to us than a falsely precise one.
              </dd>
              <dt>3. Confidence</dt>
              <dd>
                One of five levels, from very low to very high. This is about how solid your basis
                is for the estimate (direct experience, strong evidence, or mostly extrapolation).
                It's normal and expected for it to vary from item to item.
              </dd>
              <dt>4. Rationale</dt>
              <dd>
                A few sentences on where the
                technique steps into the failure's causal chain, the assumptions that drive your
                number, and when you'd expect the technique to fail. Your group will see these
                rationales, anonymised, in the discussion.
              </dd>
            </dl>

          </section>

          {/* ------------------------------------------------------- METHOD */}
          {/* <section id="guide-method" className="guide-section">
            <h2>The methodology</h2>
            <p>
              The design rests on a handful of choices, each made for a specific reason.
            </p>
            <dl className="guide-dl">
              <dt>Structured elicitation (IDEA)</dt>
              <dd>
                Private first estimates, then a discussion of anonymised estimates and reasoning,
                then private revision. This keeps the benefits of discussion (sharing evidence
                and arguments) while limiting groupthink and anchoring on whoever speaks first.
                Nobody is asked to reach consensus.
              </dd>
              <dt>One fixed scenario</dt>
              <dd>
                Everyone estimates for the same concrete setting, so differences between experts
                reflect views about the technique rather than different mental pictures.
              </dd>
              <dt>A relative quantity</dt>
              <dd>
                Published studies measure techniques against different baselines, on different
                benchmarks and metrics, so their raw numbers can't be compared directly. Asking
                for the reduction relative to one shared SFT baseline puts every item on the same
                scale.
              </dd>
              <dt>Uncertainty and reasoning</dt>
              <dd>
                The best estimate, interval, confidence and rationale together tell us not only
                what you think but how sure you are and why.
              </dd>
              <dt>Aggregation</dt>
              <dd>
                Each person's three numbers are combined into one value using the PERT mean,
                (low + 4 × best + high) ÷ 6. These are then averaged across the panel, with every
                expert weighted equally. We also combine everyone's full distributions to get a
                5th to 95th percentile band for each item, and keep all individual answers
                alongside.
              </dd>
              <dt>Why equal weights</dt>
              <dd>
                Some elicitation methods weight experts by how well they answer calibration
                questions with known answers. No such questions exist for “percentage reduction
                relative to SFT”, so weighting would have no sound basis. As a pre-planned check,
                we also compute anchor-based weights and report whether they change the results.
              </dd>
              <dt>Checking against known results (ordinal anchors)</dt>
              <dd>
                Before interpreting any estimates, we check whether the panel reproduces
                orderings that are already well established in the literature. For example,
                Constitutional Classifiers should reduce jailbreaking more than RLHF does. Each
                anchor passes or fails depending on whether the panel's estimates follow the
                expected order. Only the order is checked, not the size of the gap. This checks
                the panel and the instrument, not any individual. Passing is a necessary
                condition for trusting the estimates on items nobody can measure, though not a
                sufficient one.
              </dd>
              <dt>A simulated pilot first</dt>
              <dd>
                We ran the full protocol with LLM-simulated experts before involving anyone.
                Where the simulated panel got confused or disagreed for odd reasons, we fixed the
                wording. That way your time goes into the real questions, not into debugging
                ours.
              </dd>
            </dl>
          </section> */}

          {/* -------------------------------------------------------- REUSE */}
          {/* <section id="guide-reuse" className="guide-section">
            <h2>How this can be used beyond this study</h2>
            <p>
              We designed the method to be modular. Adding a new technique or failure mode means
              writing a new description card and a new set of items. Nothing else has to change.
              Anyone repeating or extending the study would follow the same six steps we did:
            </p>
            <ol className="guide-steps">
              <li>
                <strong>Choose items that cover the space.</strong> We placed candidates on two
                axes: does the failure happen in today's systems, and has the technique been
                deployed and measured at frontier scale? A good item set covers all four
                combinations and includes some measurable pairs as calibration.
              </li>
              <li>
                <strong>Write neutral cards.</strong> Each failure mode gets an operational
                definition, a threat model, an explicit success condition and a reference paper.
                Each technique gets a mechanism-only description drawn from its primary paper,
                with no claims about how well it works, so the description itself doesn't suggest
                an answer.
              </li>
              <li>
                <strong>Fix the scenario</strong>, or adapt it if the new failure mode needs a
                different setting.
              </li>
              <li>
                <strong>Add anchors</strong> wherever the literature supports a clear ordering.
              </li>
              <li>
                <strong>Run a simulated panel first</strong> to catch unclear wording cheaply. Our
                pipeline and prompts are open source, so this step can be reused as is.
              </li>
              <li>
                <strong>Run the human rounds</strong>, keeping a shared core of linking items so
                new results line up with earlier ones.
              </li>
            </ol>
            <p>
              Because every estimate is a reduction relative to the same SFT baseline, results
              from a later study can be placed next to this one. Over time that builds a growing
              map of techniques against failure modes, and individual cells can be revisited as
              new evidence comes in. The same approach also extends to combinations of techniques
              (how much do two safeguards achieve together?), which our pipeline already
              supports in the simulated setting.
            </p>
          </section> */}

          {/* ------------------------------------------------------ READING */}
          <section id="guide-reading" className="guide-section">
            <h2>Reading list</h2>
            <p>
              Each technique and failure mode in the survey has a short overview and a
              link to its reference paper. If you already know one well, the overview is enough.
              If it's outside your area of work, we recommend reading the paper before you
              estimate, so your judgment rests on the same evidence as the rest of the panel.
            </p>
            <h3>Failure modes</h3>
            <div className="guide-papers">
              {READING_FMS.flatMap((fm) =>
                papersOf(fm).map((p) => (
                  <div key={`${fm.id}-${p.url}`} className="guide-paper-row">
                    <span className="guide-paper-for">{fm.name}</span>
                    <PaperLink paper={p} />
                  </div>
                ))
              )}
            </div>
            <h3>Alignment techniques</h3>
            <div className="guide-papers">
              {READING_TECHS.flatMap((t) =>
                papersOf(t).map((p) => (
                  <div key={`${t.id}-${p.url}`} className="guide-paper-row">
                    <span className="guide-paper-for">{t.shortName}</span>
                    <PaperLink paper={p} />
                  </div>
                ))
              )}
            </div>
          </section>

          {/* ------------------------------------------------------ PRIVACY */}
          <section id="guide-privacy" className="guide-section">
            <h2>Your data</h2>
            {ANONYMOUS ? (
              <>
                <p>
                  <strong>The survey is anonymous.</strong> We won't be associating your name or email with your responses.
                </p>
                <ul>
                  <li>
                    <strong>What we record:</strong> your sector (as a broad category), your
                    primary role, round, track, group number in round 2, the random participant
                    ID, and your answers.
                  </li>
                  <li>
                    <strong>Who sees your reasoning:</strong> your group sees some rationales
                    during the discussion, without names.
                  </li>
                  {/* <li>
                    <strong>How long we keep it:</strong> your responses are used only during
                    this workshop to speed up aggregation, and are deleted immediately afterwards.
                  </li> */}
                </ul>
              </>
            ) : (
              <>
                <p>
                  In this version of the survey we ask for your name, email and affiliation
                  alongside your answers, so we can follow up if needed.
                </p>
                <ul>
                  <li>
                    <strong>What we record:</strong> name, email, affiliation, primary role,
                    round, track, group number in round 2, a participant ID, and your answers.
                  </li>
                  <li>
                    <strong>Who sees your reasoning:</strong> your group sees some rationales
                    during the discussion, always without names.
                  </li>
                </ul>
              </>
            )}
            <h3>Saving your progress</h3>
            <p>
              The survey saves your answers in your browser’s local storage after every change, including half-finished items. Nothing reaches us until you submit, and the saved copy is deleted when you do. To resume, open the survey on the same device and browser (not a private window) and choose “Continue where you left off”.
            </p>
            {INTEREST_FORM_URL && (
              <>
                <h3>Staying in touch</h3>
                <p>
                  To take part, get the results, or hear about future rounds, use our {" "} 
                  <a className="guide-cite" href={INTEREST_FORM_URL} target="_blank" rel="noreferrer">
                    interest form
                  </a>
                  . It runs outside this survey and is never linked to your answers. We use those
                  details only to contact you about the study and to share the results.
                </p>
              </>
            )}
          </section>

          {/* ---------------------------------------------------------- FAQ */}
          <section id="guide-faq" className="guide-section">
            <h2>Common questions</h2>
            <div className="guide-faq">
              <details>
                <summary>I'm not an expert in every technique. Should I still take part?</summary>
                <p>
                  Yes. The panel is mixed on purpose, and a view from outside a technique's own
                  community is often useful.
                </p>
              </details>
              <details>
                <summary>Can I skip an item?</summary>
                <p>
                  The survey needs an answer for every item. If you really have little to go on,
                  give your best guess with a wide interval and very low confidence, and say so
                  in the rationale. That is still informative.
                </p>
              </details>
              <details>
                <summary>Can I change an answer?</summary>
                <p>
                  Before submitting, you can return to any item from the the review page. After
                  submitting, round 2 is where you revise.
                </p>
              </details>
              <details>
                <summary>
                  A scenario or definition could be better, or something important is missing.
                </summary>
                <p>
                  We'd love to hear your feedback. Please tell us at <Email />.
                </p>
              </details>
              {INTEREST_FORM_URL && (
                <details>
                  <summary>I am interested in participating. How do I sign up?</summary>
                  <p>
                    Yes, please register through our{' '}
                    <a className="guide-cite" href={INTEREST_FORM_URL} target="_blank" rel="noreferrer">
                      interest form
                    </a>{' '}
                    and we'll be in touch about joining an upcoming group.
                  </p>
                </details>
              )}
              <details>
                <summary>I lost my participant ID.</summary>
                <p>
                  Email us at <Email /> before round 2 starts. We can't look the
                  code up, but we'll tell you how to continue.
                </p>
              </details>
            </div>
          </section>

          <div className="guide-end">
            {onStart ? (
              <button className="btn-primary btn-lg" onClick={onStart}>
                Begin the survey <ChevronRight size={16} strokeWidth={2.2} />
              </button>
            ) : (
              <button className="btn-primary" onClick={onClose}>
                Back to the survey
              </button>
            )}
          </div>
        </article>
      </div>
    </div>
  );
}
