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
