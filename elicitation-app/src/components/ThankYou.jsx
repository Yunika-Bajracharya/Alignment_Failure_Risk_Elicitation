import React, { useState } from 'react';
import { CheckCircle2, Download, Check, Brain, Shield, Scale, Eye, Zap, BookOpen } from 'lucide-react';

const CONFIDENCE_LABELS = { 1: 'Very Low', 2: 'Low', 3: 'Moderate', 4: 'High', 5: 'Very High' };

function buildJSON(expert, selectedFMs, alignmentTechniques, assessments) {
  return {
    metadata: {
      exportedAt: new Date().toISOString(),
      studyVersion: '1.0',
      tool: 'AI Safety Elicitation App',
    },
    expert,
    assessments: selectedFMs.map((fm) => ({
      failureMode: {
        id: fm.id,
        name: fm.name,
        scenarioLabel: fm.scenarioLabel,
        deploymentScenario: fm.deploymentScenario.name,
      },
      techniqueAssessments: alignmentTechniques.map((tech) => {
        const a = assessments[fm.id]?.[tech.id] || {};
        return {
          techniqueId: tech.id,
          techniqueName: tech.name,
          pointEstimate: a.pointEstimate !== undefined ? a.pointEstimate : null,
          lowerBound: a.lowerBound || null,
          upperBound: a.upperBound || null,
          confidence: a.confidence || null,
          confidenceLabel: a.confidence ? CONFIDENCE_LABELS[a.confidence] : null,
          rationale: a.rationale || '',
          notApplicable: a.notApplicable || false,
        };
      }),
    })),
  };
}

function buildCSV(expert, selectedFMs, alignmentTechniques, assessments) {
  const rows = [];
  rows.push([
    'ExpertName', 'ExpertRole', 'ExpertAffiliation', 'ExpertYearsExperience',
    'FailureModeId', 'FailureModeName', 'ScenarioLabel', 'DeploymentScenario',
    'TechniqueId', 'TechniqueName',
    'PointEstimate', 'LowerBound', 'UpperBound',
    'ConfidenceLevel', 'ConfidenceLabel',
    'Rationale', 'NotApplicable'
  ].join(','));

  selectedFMs.forEach((fm) => {
    alignmentTechniques.forEach((tech) => {
      const a = assessments[fm.id]?.[tech.id] || {};
      const escapeCSV = (v) => {
        const s = String(v ?? '');
        return s.includes(',') || s.includes('"') || s.includes('\n')
          ? `"${s.replace(/"/g, '""')}"`
          : s;
      };
      rows.push([
        escapeCSV(expert.name),
        escapeCSV(expert.role),
        escapeCSV(expert.affiliation),
        escapeCSV(expert.yearsExperience),
        escapeCSV(fm.id),
        escapeCSV(fm.name),
        escapeCSV(fm.scenarioLabel),
        escapeCSV(fm.deploymentScenario.name),
        escapeCSV(tech.id),
        escapeCSV(tech.name),
        escapeCSV(a.pointEstimate ?? ''),
        escapeCSV(a.lowerBound ?? ''),
        escapeCSV(a.upperBound ?? ''),
        escapeCSV(a.confidence ?? ''),
        escapeCSV(a.confidence ? CONFIDENCE_LABELS[a.confidence] : ''),
        escapeCSV(a.rationale ?? ''),
        escapeCSV(a.notApplicable ? 'true' : 'false'),
      ].join(','));
    });
  });

  return rows.join('\n');
}

function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function ThankYou({ expert, selectedFMs, alignmentTechniques, assessments }) {
  const [downloaded, setDownloaded] = useState({ json: false, csv: false });

  const handleDownloadJSON = () => {
    const data = buildJSON(expert, selectedFMs, alignmentTechniques, assessments);
    const filename = `elicitation_${expert.name.replace(/\s+/g, '_')}_${new Date().toISOString().slice(0, 10)}.json`;
    downloadFile(JSON.stringify(data, null, 2), filename, 'application/json');
    setDownloaded((d) => ({ ...d, json: true }));
  };

  const handleDownloadCSV = () => {
    const csv = buildCSV(expert, selectedFMs, alignmentTechniques, assessments);
    const filename = `elicitation_${expert.name.replace(/\s+/g, '_')}_${new Date().toISOString().slice(0, 10)}.csv`;
    downloadFile(csv, filename, 'text/csv;charset=utf-8;');
    setDownloaded((d) => ({ ...d, csv: true }));
  };

  const totalAnswered = selectedFMs.reduce((acc, fm) => {
    return acc + alignmentTechniques.filter((t) => assessments[fm.id]?.[t.id]).length;
  }, 0);

  return (
    <div className="thankyou-page">
      {/* Floating icon decoration */}
      <div className="thankyou-decoration" aria-hidden="true">
        {[Brain, Shield, Scale, Eye, Zap, BookOpen].map((Icon, i) => (
          <span key={i} className="decoration-icon" style={{ bottom: '-5%', animationDelay: `${i * 0.8}s` }}>
            <Icon size={26} strokeWidth={1.5} />
          </span>
        ))}
      </div>

      <div className="thankyou-card">
        <div className="thankyou-icon">
          <CheckCircle2 size={36} strokeWidth={1.5} />
        </div>
        <h1>Thank You, {expert.name.split(" ")[0]}!</h1>
        <p className="thankyou-subtitle">
          Your expert estimates have been recorded and are ready to download. Your contribution
          helps build a rigorous evidence base for AI safety policy and research.
        </p>

        {/* Summary stats */}
        <div className="thankyou-stats">
          <div className="stat-box">
            <span className="stat-number">{selectedFMs.length}</span>
            <span className="stat-label">Scenarios assessed</span>
          </div>
          <div className="stat-box">
            <span className="stat-number">{totalAnswered}</span>
            <span className="stat-label">Assessments completed</span>
          </div>
          <div className="stat-box">
            <span className="stat-number">{alignmentTechniques.length}</span>
            <span className="stat-label">Techniques evaluated</span>
          </div>
        </div>

        {/* Download buttons */}
        <div className="download-section">
          <h3>Download Your Responses</h3>
          <p>Save your responses in one or both formats. No data has been sent externally.</p>
          <div className="download-buttons">
            <button
              className={`btn-download btn-json ${downloaded.json ? 'downloaded' : ''}`}
              onClick={handleDownloadJSON}
            >
              {downloaded.json
                ? <><Check size={14} style={{ verticalAlign: 'middle' }} /> Downloaded</>
                : <><Download size={14} style={{ verticalAlign: 'middle' }} /> Download JSON</>}
              <span className="download-desc">Structured format, ideal for analysis</span>
            </button>
            <button
              className={`btn-download btn-csv ${downloaded.csv ? 'downloaded' : ''}`}
              onClick={handleDownloadCSV}
            >
              {downloaded.csv
                ? <><Check size={14} style={{ verticalAlign: 'middle' }} /> Downloaded</>
                : <><Download size={14} style={{ verticalAlign: 'middle' }} /> Download CSV</>}
              <span className="download-desc">Spreadsheet format, opens in Excel</span>
            </button>
          </div>
        </div>

        {/* Next steps */}
        <div className="next-steps">
          <h3>Next Steps</h3>
          <ul>
            <li>Please send your exported file(s) to the study coordinators.</li>
            <li>If you wish to revise any responses, reload the page to start a new session.</li>
            <li>Your responses will be aggregated with those of other experts for analysis.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
