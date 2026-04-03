import React from 'react';
import { useAssessment } from '../hooks/useAssessment';
import { AssessmentForm } from '../../../components/assessment/AssessmentForm';
import { ReportViewer } from '../../../components/assessment/ReportViewer';

export const HomePage: React.FC = () => {
  const { report, loading, error, submitAssessment, resetAssessment } = useAssessment();

  return (
    <>
      {error && (
        <div style={{ color: '#ff4d4f', marginBottom: 16, padding: '8px 16px', background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: '6px' }}>
          {error}
        </div>
      )}
      {report ? (
        <ReportViewer report={report} onBack={resetAssessment} isStreaming={loading} />
      ) : (
        <AssessmentForm onSubmit={submitAssessment} isLoading={loading} />
      )}
    </>
  );
};
