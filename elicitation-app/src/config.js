// Content variant for the survey cards.
//
// Mirrors the LLM-elicitation setup, where a config selects between the
// framing-controlled "descriptive" input files and the original detailed ones.
//
//   'neutral'  -> paper-anchored, framing-controlled cards (matches
//                 input_data/*_descriptive.yaml). Technique cards show only
//                 Overview + Deployment; failure modes use the generalized
//                 "Deployed High-Stakes Advisory System" scenario.
//   'detailed' -> richer cards with Mechanism / Failure Pathways / Limitations
//                 tabs, and the original domain scenarios (e.g. biosecurity).
//
// Switch without editing code, in priority order:
//   1. URL query param (live, no rebuild):  ?variant=detailed
//   2. Build/dev env var:                   VITE_CONTENT_VARIANT=detailed npm run dev
//   3. The default below.
const ALLOWED = ['neutral', 'detailed'];
const DEFAULT_VARIANT = 'neutral';

function resolveVariant() {
  if (typeof window !== 'undefined' && window.location) {
    const q = new URLSearchParams(window.location.search).get('variant');
    if (ALLOWED.includes(q)) return q;
  }
  const env = import.meta.env?.VITE_CONTENT_VARIANT;
  if (ALLOWED.includes(env)) return env;
  return DEFAULT_VARIANT;
}

export const CONTENT_VARIANT = resolveVariant();

// Anonymous mode (default ON). When on, the survey collects NO name and NO email,
// and asks for the employer only as a coarse, non-identifying category.
//   true  -> anonymous: no name/email, affiliation = sector category
//   false -> collect full name, email, and free-text affiliation
// Override in priority order: ?anonymous=false URL param -> VITE_ANONYMOUS env -> default.
const DEFAULT_ANONYMOUS = true;

function resolveAnonymous() {
  const read = (v) => (v === 'true' || v === '1' ? true : v === 'false' || v === '0' ? false : undefined);
  if (typeof window !== 'undefined' && window.location) {
    const q = read(new URLSearchParams(window.location.search).get('anonymous'));
    if (q !== undefined) return q;
  }
  const env = read(import.meta.env?.VITE_ANONYMOUS);
  if (env !== undefined) return env;
  return DEFAULT_ANONYMOUS;
}

export const ANONYMOUS = resolveAnonymous();

// Optional profile fields (default OFF). Our evaluation does not use these, so by
// default the survey neither shows nor records them. Enable a field if you want it.
//   COLLECT_EXPERTISE_AREAS  -> the multi-select "Expertise Areas" checklist
//   COLLECT_YEARS_EXPERIENCE -> the "Years of Experience in AI Safety / ML" select
// Override per field, in priority order:
//   1. URL query param:  ?expertiseAreas=true  /  ?yearsExperience=true
//   2. Build/dev env var: VITE_COLLECT_EXPERTISE_AREAS / VITE_COLLECT_YEARS_EXPERIENCE
//   3. The default below.
function resolveBool(param, envValue, def) {
  const read = (v) => (v === 'true' || v === '1' ? true : v === 'false' || v === '0' ? false : undefined);
  if (typeof window !== 'undefined' && window.location) {
    const q = read(new URLSearchParams(window.location.search).get(param));
    if (q !== undefined) return q;
  }
  const env = read(envValue);
  if (env !== undefined) return env;
  return def;
}

export const COLLECT_EXPERTISE_AREAS = resolveBool(
  'expertiseAreas', import.meta.env?.VITE_COLLECT_EXPERTISE_AREAS, false);
export const COLLECT_YEARS_EXPERIENCE = resolveBool(
  'yearsExperience', import.meta.env?.VITE_COLLECT_YEARS_EXPERIENCE, false);

// Where participants send questions and feedback.
export const CONTACT_EMAIL = 'bajracharya.yunika@gmail.com';

// Optional expression-of-interest form (Google Form), kept separate from the
// survey so contact details are never linked to responses. Empty = links hidden.
export const INTEREST_FORM_URL = 'https://forms.gle/mGAKowiN2rY976nz6';
