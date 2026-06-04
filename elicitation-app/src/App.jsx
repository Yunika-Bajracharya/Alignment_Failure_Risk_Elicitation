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
  expertiseAreas: [],
};

export default function App() {
  const [step, setStep] = useState(STEPS.LANDING);
  const [expert, setExpert] = useState(initialExpert);
  const [selectedFMIds, setSelectedFMIds] = useState([]);
  // { [fmId]: { [techniqueId]: { pointEstimate, lowerBound, upperBound, confidence, rationale, notApplicable } } }
  const [assessments, setAssessments] = useState({});
  const [currentFMIndex, setCurrentFMIndex] = useState(0);
  const [currentTechIndex, setCurrentTechIndex] = useState(0);

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

  const handleSubmit = () => {
    setStep(STEPS.COMPLETE);
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
            onNext={() => setStep(STEPS.SCENARIO_SELECTION)}
          />
        )}
        {step === STEPS.SCENARIO_SELECTION && (
          <ScenarioSelection
            selectedFMIds={selectedFMIds}
            setSelectedFMIds={setSelectedFMIds}
            onNext={handleGoToDeployment}
            onBack={() => setStep(STEPS.EXPERT_PROFILE)}
          />
        )}
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
