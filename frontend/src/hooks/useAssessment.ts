import { useState, useCallback } from 'react';
import { UserInput, FinalReport } from '../models';
import { assessDevelopment } from '../api/client';

export const useAssessment = () => {
  const [report, setReport] = useState<FinalReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitAssessment = useCallback(async (data: UserInput) => {
    setLoading(true);
    setError(null);
    try {
      const result = await assessDevelopment(data);
      if (typeof result === 'string') {
        setReport({ markdown_content: result, structured_data: {} });
      } else {
        setReport(result);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || err.message || '发生错误，请重试');
    } finally {
      setLoading(false);
    }
  }, []);

  const resetAssessment = useCallback(() => {
    setReport(null);
    setError(null);
  }, []);

  return {
    report,
    loading,
    error,
    submitAssessment,
    resetAssessment
  };
};
