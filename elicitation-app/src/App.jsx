import React, { useState, useEffect } from 'react';
import LandingPage from './components/LandingPage';
import ExpertProfile from './components/ExpertProfile';
import ScenarioSelection from './components/ScenarioSelection';
import DeploymentScenario from './components/DeploymentScenario';
import AssessmentView from './components/AssessmentView';
import ReviewSubmit from './components/ReviewSubmit';
import ThankYou from './components/ThankYou';
import Navbar from './components/Navbar';
import StudyGuide from './components/StudyGuide';
import { loadDraft, saveDraft, clearDraft, countAnswered } from './draft';
import { alignmentTechniques } from './data/alignmentTechniques';
import { failureModes } from './data/failureModes';
import { ANONYMOUS, COLLECT_EXPERTISE_AREAS, COLLECT_YEARS_EXPERIENCE } from './config';
import { createClient } from '@supabase/supabase-js';
import uuid from 'react-uuid';

const supabaseUrl = import.meta.env.VITE_SUPABASE_PROJECT_URL;
const supabaseKey = import.meta.env.VITE_PUBLISHABLE_API_KEY;

const supabase = supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null;

const techniqueMapping = [
  { id: 'jailbreaking', alignmentTechniques: ['rlhf', 'adversarial_training', 'constitutional_classifiers', 'circuit_breakers'] },
  { id: 'sycophancy', alignmentTechniques: ['rlhf', 'constitutional_ai'] },
  { id: 'deceptive_alignment', alignmentTechniques: ['rlhf', 'circuit_breakers', 'alignment_pretraining', 'ai_debate', 'cot_monitoring', 'deliberative_alignment'] },
  { id: 'sleeper_agents_backdoor', alignmentTechniques: ['rlhf', 'circuit_breakers', 'alignment_pretraining', 'ai_debate', 'cot_monitoring', 'deliberative_alignment'] },
];

const getTechniquesForFailureMode = (fmId) => {
  const mapping = techniqueMapping.find((m) => m.id === fmId);
  if (!mapping) return alignmentTechniques;
  return alignmentTechniques.filter((t) => mapping.alignmentTechniques.includes(t.id));
};

const toNullableNumber = (value) => {
  if (value === '' || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const getSubmissionGroupId = (expert) => (expert.round === '2' ? toNullableNumber(expert.groupId) : null);

const getSubmissionRole = (expert) => {
  if (expert.role === 'Other') {
    return (expert.otherRole || '').trim() || null;
  }
  return expert.role || null;
};

async function persistSubmissionToSupabase({ expert, selectedFMs, assessments }) {
  if (!supabase) {
    throw new Error(
      'Supabase is not configured. Set VITE_SUPABASE_PROJECT_URL and VITE_PUBLISHABLE_API_KEY in .env.local'
    );
  }

  const expertPayload = {
    // In anonymous mode these are never persisted, regardless of UI state.
    name: ANONYMOUS ? null : (expert.name || null),
    email: ANONYMOUS ? null : (expert.email || null),
    affiliation: (expert.affiliation || '').trim(),
    role: getSubmissionRole(expert),
    years_experience: COLLECT_YEARS_EXPERIENCE ? (expert.yearsExperience || null) : null,
    round: toNullableNumber(expert.round),
    track: expert.track || null,
    expertise_areas: COLLECT_EXPERTISE_AREAS ? (expert.expertiseAreas || null) : null,
    group_id: getSubmissionGroupId(expert),
    personal_id: expert.personalId || null,
  };

  const run_id = uuid();
  
  const { data: insertedExpert, error: expertError } = await supabase
    .from('experts')
    .insert(expertPayload)
    .select('id')
    .single();
  if (expertError) throw expertError;

  const assessmentsToInsert = [];
  selectedFMs.forEach((fm) => {
    // select techniques as per failure mode
    const techniquesForFM = getTechniquesForFailureMode(fm.id);
    techniquesForFM.forEach((tech) => {
      const a = assessments[fm.id]?.[tech.id];
      if (a) {
        assessmentsToInsert.push({
          run_id: run_id,
          expert_id: insertedExpert.id,
          round: toNullableNumber(expert.round),
          group_id: getSubmissionGroupId(expert),
          personal_id: expert.personalId || null,
          track: expert.track || null,
          failure_mode_id: fm.id,
          technique_id: tech.id,
          point_estimate: toNullableNumber(a.pointEstimate),
          lower_bound: toNullableNumber(a.lowerBound),
          upper_bound: toNullableNumber(a.upperBound),
          confidence: toNullableNumber(a.confidence),
          rationale: a.rationale || null,
        });
      }
    });
  });

  if (assessmentsToInsert.length > 0) {
    const { error: assessmentsError } = await supabase
      .from('elicitation_runs')
      .insert(assessmentsToInsert);
    if (assessmentsError) throw assessmentsError;
  }

  return run_id;
}

export const STEPS = {
  LANDING: 'LANDING',
  EXPERT_PROFILE: 'EXPERT_PROFILE',
  SCENARIO_SELECTION: 'SCENARIO_SELECTION',
  DEPLOYMENT_SCENARIO: 'DEPLOYMENT_SCENARIO',
  ASSESSMENT: 'ASSESSMENT',
  REVIEW: 'REVIEW',
  COMPLETE: 'COMPLETE',
};

const initialExpert = {
  name: '',
  email: '',
  affiliation: '',
  role: '',
  track: '',
  otherRole: '',
  yearsExperience: '',
  round: '',
  expertiseAreas: [],
  groupId: '',
  personalId: '',
};

const fmIdsForTrack = (track) => {
  if (track === "A") return ["jailbreaking", "sycophancy", "sleeper_agents_backdoor"];
  if (track === "B") return ["jailbreaking", "sycophancy", "deceptive_alignment"];
  return [];
};

const itemCountForTrack = (track) =>
  fmIdsForTrack(track).reduce((sum, id) => sum + getTechniquesForFailureMode(id).length, 0);

export default function App() {
  const [step, setStep] = useState(STEPS.LANDING);
  const [expert, setExpert] = useState(initialExpert);
  const selectedFMIds = fmIdsForTrack(expert.track);
  // { [fmId]: { [techniqueId]: { pointEstimate, lowerBound, upperBound, confidence, rationale, notApplicable } } }
  const [assessments, setAssessments] = useState({});
  const [currentFMIndex, setCurrentFMIndex] = useState(0);
  const [currentTechIndex, setCurrentTechIndex] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [showGuide, setShowGuide] = useState(false);
  // A response saved in this browser from an earlier visit (see draft.js).
  const [savedDraft, setSavedDraft] = useState(() => loadDraft());
  // The item currently being edited, kept so a half-filled item survives a reload.
  const [itemDraft, setItemDraft] = useState(null);

  const isInProgress =
    step !== STEPS.LANDING && step !== STEPS.COMPLETE && Boolean(expert.round && expert.track);

  // Autosave: every change to the response is written to this browser.
  useEffect(() => {
    if (!isInProgress) return;
    saveDraft({ step, expert, assessments, currentFMIndex, currentTechIndex, itemDraft });
  }, [isInProgress, step, expert, assessments, currentFMIndex, currentTechIndex, itemDraft]);

  const resumeDraft = () => {
    const d = savedDraft;
    if (!d) return;
    setExpert({ ...initialExpert, ...d.expert });
    setAssessments(d.assessments || {});
    setCurrentFMIndex(d.currentFMIndex || 0);
    setCurrentTechIndex(d.currentTechIndex || 0);
    setItemDraft(d.itemDraft || null);
    const resumable = STEPS[d.step] && d.step !== STEPS.LANDING && d.step !== STEPS.COMPLETE;
    setStep(resumable ? d.step : STEPS.EXPERT_PROFILE);
    setSavedDraft(null);
  };

  const startOver = () => {
    clearDraft();
    setSavedDraft(null);
    setExpert(initialExpert);
    setAssessments({});
    setCurrentFMIndex(0);
    setCurrentTechIndex(0);
    setItemDraft(null);
    setStep(STEPS.EXPERT_PROFILE);
  };

  const selectedFMs = failureModes.filter((fm) => selectedFMIds.includes(fm.id));

  // techniques that apply to failure modes currently being assessed
  const currentFM = selectedFMs[currentFMIndex];
  const currentTechniques = getTechniquesForFailureMode(currentFM?.id);

  // total/completed steps sum each fm's own technique count
  const totalSteps = selectedFMs.reduce((sum, fm) => sum + getTechniquesForFailureMode(fm.id).length, 0);
  const completedSteps =
    selectedFMs.slice(0, currentFMIndex).reduce((sum, fm) => sum + getTechniquesForFailureMode(fm.id).length, 0) +
    currentTechIndex;

  const updateAssessment = (fmId, techId, data) => {
    setAssessments((prev) => ({
      ...prev,
      [fmId]: {
        ...(prev[fmId] || {}),
        [techId]: data,
      },
    }));
  };

  const getAssessment = (fmId, techId) => {
    if (itemDraft && itemDraft.fmId === fmId && itemDraft.techId === techId) return itemDraft.data;
    return assessments[fmId]?.[techId] || null;
  };

  const goNext = () => {
    const techsForCurrentFM = getTechniquesForFailureMode(selectedFMs[currentFMIndex].id);
    const isLastTech = currentTechIndex >= techsForCurrentFM.length - 1;
    const isLastFM = currentFMIndex >= selectedFMs.length - 1;

    if (!isLastTech) {
      setCurrentTechIndex((i) => i + 1);
    } else if (!isLastFM) {
      setCurrentFMIndex((i) => i + 1);
      setCurrentTechIndex(0);
      setStep(STEPS.DEPLOYMENT_SCENARIO);
    } else {
      setStep(STEPS.REVIEW);
    }
  };

  const goPrev = () => {
    if (currentTechIndex > 0) {
      setCurrentTechIndex((i) => i - 1);
    } else if (currentFMIndex > 0) {
      setStep(STEPS.DEPLOYMENT_SCENARIO);
    } else {
      setStep(STEPS.DEPLOYMENT_SCENARIO);
    }
  };

  const handleGoToDeployment = () => {
    setCurrentFMIndex(0);
    setCurrentTechIndex(0);
    setStep(STEPS.DEPLOYMENT_SCENARIO);
  };

  const handleStartAssessment = () => {
    setCurrentTechIndex(0);
    setStep(STEPS.ASSESSMENT);
  };

  const handleDeploymentBack = () => {
    if (currentFMIndex > 0) {
      const prevFM = selectedFMs[currentFMIndex - 1];
      const prevTechs = getTechniquesForFailureMode(prevFM.id);
      setCurrentFMIndex((i) => i - 1);
      setCurrentTechIndex(prevTechs.length - 1);
      setStep(STEPS.ASSESSMENT);
      return;
    }

    // setStep(STEPS.SCENARIO_SELECTION);
    setStep(STEPS.EXPERT_PROFILE);

  };

  const handleSubmit = async () => {
    setSubmitError('');
    setIsSubmitting(true);

    try {
      await persistSubmissionToSupabase({
        expert,
        selectedFMs,
        assessments,
      });
      clearDraft();
      setItemDraft(null);
      setStep(STEPS.COMPLETE);
    } catch (error) {
      setSubmitError(error?.message || 'Failed to save submission to DB.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const showNavbar = step !== STEPS.LANDING && step !== STEPS.COMPLETE;

  return (
    <div className="app">
      {showNavbar && (
        <Navbar
          step={step}
          expert={expert}
          setStep={setStep}
          currentFM={selectedFMs[currentFMIndex]}
          currentTech={currentTechniques[currentTechIndex]}
          totalSteps={totalSteps}
          completedSteps={completedSteps}
          onOpenGuide={() => setShowGuide(true)}
          autosaved={isInProgress}
        />
      )}
      <main className={`main-content ${step === STEPS.LANDING ? 'no-nav' : ''}`}>
        {step === STEPS.LANDING && (
          <LandingPage
            onStart={savedDraft ? resumeDraft : () => setStep(STEPS.EXPERT_PROFILE)}
            onOpenGuide={() => setShowGuide(true)}
            draft={
              savedDraft && {
                round: savedDraft.expert?.round,
                track: savedDraft.expert?.track,
                answered: countAnswered(savedDraft.assessments),
                total: itemCountForTrack(savedDraft.expert?.track),
                savedAt: savedDraft.savedAt,
              }
            }
            onStartOver={startOver}
          />
        )}
        {step === STEPS.EXPERT_PROFILE && (
          <ExpertProfile
            expert={expert}
            setExpert={setExpert}
            onNext={() => setStep(STEPS.DEPLOYMENT_SCENARIO)}
          />
        )}
        {/* {step === STEPS.SCENARIO_SELECTION && (
          <ScenarioSelection
            selectedFMIds={selectedFMIds}
            setSelectedFMIds={setSelectedFMIds}
            onNext={handleGoToDeployment}
            onBack={() => setStep(STEPS.EXPERT_PROFILE)}
          />
        )} */}
        {step === STEPS.DEPLOYMENT_SCENARIO && (
          <DeploymentScenario
            failureMode={selectedFMs[currentFMIndex]}
            fmIndex={currentFMIndex}
            totalFMs={selectedFMs.length}
            onNext={handleStartAssessment}
            onBack={handleDeploymentBack}
          />
        )}
        {step === STEPS.ASSESSMENT && selectedFMs.length > 0 && (
          <AssessmentView
            failureMode={selectedFMs[currentFMIndex]}
            technique={currentTechniques[currentTechIndex]}
            fmIndex={currentFMIndex}
            techIndex={currentTechIndex}
            totalFMs={selectedFMs.length}
            totalTechs={currentTechniques.length}
            savedAssessment={getAssessment(
              selectedFMs[currentFMIndex]?.id,
              currentTechniques[currentTechIndex]?.id
            )}
            onSave={(data) =>
              updateAssessment(
                selectedFMs[currentFMIndex].id,
                currentTechniques[currentTechIndex].id,
                data
              )
            }
            onDraftChange={(fmId, techId, data) => setItemDraft({ fmId, techId, data })}
            onNext={goNext}
            onPrev={goPrev}
          />
        )}
        {step === STEPS.REVIEW && (
          <ReviewSubmit
            expert={expert}
            selectedFMs={selectedFMs}
            getTechniquesForFailureMode={getTechniquesForFailureMode}
            assessments={assessments}
            isSubmitting={isSubmitting}
            submitError={submitError}
            onBack={() => {
              const lastFM = selectedFMs[selectedFMs.length - 1];
              setCurrentFMIndex(selectedFMs.length - 1);
              setCurrentTechIndex(getTechniquesForFailureMode(lastFM?.id).length - 1);
              setStep(STEPS.ASSESSMENT);
            }}
            onEdit={(fmIndex, techIndex) => {
              setCurrentFMIndex(fmIndex);
              setCurrentTechIndex(techIndex);
              setStep(STEPS.ASSESSMENT);
            }}
            onSubmit={handleSubmit}
          />
        )}
        {step === STEPS.COMPLETE && (
          <ThankYou
            expert={expert}
            selectedFMs={selectedFMs}
            getTechniquesForFailureMode={getTechniquesForFailureMode}
            assessments={assessments}
          />
        )}
      </main>
      {showGuide && (
        <StudyGuide
          onClose={() => setShowGuide(false)}
          onStart={
            step === STEPS.LANDING
              ? () => {
                  setShowGuide(false);
                  setStep(STEPS.EXPERT_PROFILE);
                }
              : undefined
          }
        />
      )}
    </div>
  );
}
