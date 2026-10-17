// Saves an in-progress response in this browser so a participant can close the
// tab and come back later. The draft lives only in
// localStorage on this device and is cleared once the response is submitted.
const DRAFT_KEY = 'elicitation_draft_v1';
const DRAFT_VERSION = 1;

export function loadDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const draft = JSON.parse(raw);
    return draft && draft.version === DRAFT_VERSION ? draft : null;
  } catch {
    return null;
  }
}

export function saveDraft(data) {
  try {
    localStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({ version: DRAFT_VERSION, savedAt: new Date().toISOString(), ...data })
    );
  } catch {
    /* storage full or blocked: the survey still works, it just won't resume */
  }
}

export function clearDraft() {
  try {
    localStorage.removeItem(DRAFT_KEY);
  } catch {
    /* ignore */
  }
}

export function countAnswered(assessments) {
  return Object.values(assessments || {}).reduce(
    (n, byTech) => n + Object.keys(byTech || {}).length,
    0
  );
}
