import React, { useState, useEffect } from 'react';
import LandingPage from './components/LandingPage';
import ExpertProfile from './components/ExpertProfile';
import ScenarioSelection from './components/ScenarioSelection';
import DeploymentScenario from './components/DeploymentScenario';
import AssessmentView from './components/AssessmentView';
import ReviewSubmit from './components/ReviewSubmit';
import ThankYou from './components/ThankYou';
import Navbar from './components/Navbar';
import { alignmentTechniques } from './data/alignmentTechniques';
import { failureModes } from './data/failureModes';
import { createClient } from '@supabase/supabase-js';

import uuid from 'react-uuid';

const supabaseUrl = import.meta.env.VITE_SUPABASE_PROJECT_URL;
const supabaseKey = import.meta.env.VITE_PUBLISHABLE_API_KEY;

const supabase = supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null;

const toNullableNumber = (value) => {
  if (value === '' || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const getSubmissionGroupId = (expert) => (expert.round === '2' ? toNullableNumber(expert.groupId) : null);

async function persistSubmissionToSupabase({ expert, selectedFMs, alignmentTechniques, assessments }) {
  if (!supabase) {
    throw new Error(
      'Supabase is not configured. Set VITE_SUPABASE_PROJECT_URL and VITE_PUBLISHABLE_API_KEY in .env.local'
    );
  }

  const expertPayload = {
    name: expert.name,
    email: expert.email || null,
    affiliation: expert.affiliation || null,
    role: expert.role || null,
    other_role: expert.otherRole || null,
    years_experience: expert.yearsExperience || null,
    round: toNullableNumber(expert.round),
    expertise_areas: expert.expertiseAreas || null,
    group_id: getSubmissionGroupId(expert),
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
    alignmentTechniques.forEach((tech) => {
      const a = assessments[fm.id]?.[tech.id];
      if (a) {
        assessmentsToInsert.push({
          run_id: run_id,
          expert_id: insertedExpert.id,
          round: toNullableNumber(expert.round),
          group_id: getSubmissionGroupId(expert),
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
  otherRole: '',
  yearsExperience: '',
  round: '',
  expertiseAreas: [],
  groupId: '',
};

export default function App() {
  const [step, setStep] = useState(STEPS.LANDING);
  const [expert, setExpert] = useState(initialExpert);
  // const [selectedFMIds, setSelectedFMIds] = useState([]);
  const selectedFMIds = ["jailbreaking", "deceptive_alignment"];
  // { [fmId]: { [techniqueId]: { pointEstimate, lowerBound, upperBound, confidence, rationale, notApplicable } } }
  const [assessments, setAssessments] = useState({});
  const [currentFMIndex, setCurrentFMIndex] = useState(0);
  const [currentTechIndex, setCurrentTechIndex] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  const selectedFMs = failureModes.filter((fm) => selectedFMIds.includes(fm.id));
  const totalSteps = selectedFMs.length * alignmentTechniques.length;
  const completedSteps =
    selectedFMs.slice(0, currentFMIndex).length * alignmentTechniques.length +
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
    return assessments[fmId]?.[techId] || null;
  };

  const goNext = () => {
    const isLastTech = currentTechIndex >= alignmentTechniques.length - 1;
    const isLastFM = currentFMIndex >= selectedFMs.length - 1;

    if (!isLastTech) {
      setCurrentTechIndex((i) => i + 1);
    } else if (!isLastFM) {
      setCurrentFMIndex((i) => i + 1);
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
      setCurrentFMIndex((i) => i - 1);
      setCurrentTechIndex(alignmentTechniques.length - 1);
      setStep(STEPS.ASSESSMENT);
      return;
    }

    setStep(STEPS.SCENARIO_SELECTION);
  };

  const handleSubmit = async () => {
    setSubmitError('');
    setIsSubmitting(true);

    try {
      await persistSubmissionToSupabase({
        expert,
        selectedFMs,
        alignmentTechniques,
        assessments,
      });
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
          currentTech={alignmentTechniques[currentTechIndex]}
          totalSteps={totalSteps}
          completedSteps={completedSteps}
        />
      )}
      <main className={`main-content ${step === STEPS.LANDING ? 'no-nav' : ''}`}>
        {step === STEPS.LANDING && (
          <LandingPage onStart={() => setStep(STEPS.EXPERT_PROFILE)} />
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
            // onBack={handleDeploymentBack}
            onBack={() => setStep(STEPS.EXPERT_PROFILE)}
          />
        )}
        {step === STEPS.ASSESSMENT && selectedFMs.length > 0 && (
          <AssessmentView
            failureMode={selectedFMs[currentFMIndex]}
            technique={alignmentTechniques[currentTechIndex]}
            fmIndex={currentFMIndex}
            techIndex={currentTechIndex}
            totalFMs={selectedFMs.length}
            totalTechs={alignmentTechniques.length}
            savedAssessment={getAssessment(
              selectedFMs[currentFMIndex]?.id,
              alignmentTechniques[currentTechIndex]?.id
            )}
            onSave={(data) =>
              updateAssessment(
                selectedFMs[currentFMIndex].id,
                alignmentTechniques[currentTechIndex].id,
                data
              )
            }
            onNext={goNext}
            onPrev={goPrev}
          />
        )}
        {step === STEPS.REVIEW && (
          <ReviewSubmit
            expert={expert}
            selectedFMs={selectedFMs}
            alignmentTechniques={alignmentTechniques}
            assessments={assessments}
            isSubmitting={isSubmitting}
            submitError={submitError}
            onBack={() => {
              setCurrentFMIndex(selectedFMs.length - 1);
              setCurrentTechIndex(alignmentTechniques.length - 1);
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
            alignmentTechniques={alignmentTechniques}
            assessments={assessments}
          />
        )}
      </main>
    </div>
  );
}
