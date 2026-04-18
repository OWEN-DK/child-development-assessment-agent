import { useState, useCallback, useRef } from 'react';
import { extractApiError } from '@shared/lib/notification';
import { assessDevelopment, assessDevelopmentStream } from '../../../api/assessment';
import type { UserInput, FinalReport, StreamingReportData } from '@entities/assessment/types';

interface UseAssessmentReturn {
  report: FinalReport | null;
  loading: boolean;
  error: string | null;
  streamingContent: string;
  streamingData: StreamingReportData | null;
  submitAssessment: (data: UserInput, useStreaming?: boolean) => Promise<void>;
  resetAssessment: () => void;
}

export const useAssessment = (): UseAssessmentReturn => {
  const [report, setReport] = useState<FinalReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState<string>('');
  const [streamingData, setStreamingData] = useState<StreamingReportData | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const submitAssessment = useCallback(async (data: UserInput, useStreaming: boolean = true) => {
    setLoading(true);
    setError(null);
    setStreamingContent('');
    setStreamingData(null);
    setReport(null);

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    if (!useStreaming) {
      try {
        const result = await assessDevelopment(data);
        if (typeof result === 'string') {
          setReport({ markdown_content: result, structured_data: {} });
        } else {
          setReport(result);
        }
      } catch (err: any) {
        console.error(err);
        const apiError = extractApiError(err);
        setError(apiError.message || '发生错误，请重试');
      } finally {
        setLoading(false);
      }
      return;
    }

    try {
      abortControllerRef.current = new AbortController();

      await assessDevelopmentStream(
        data,
        (data) => {
          setStreamingData(data);
          setReport({
            markdown_content: '',
            structured_data: data,
          });
        },
        (chunk) => {
          setStreamingContent((prev) => prev + chunk);
          setReport((prev: FinalReport | null) => prev ? {
            ...prev,
            markdown_content: prev.markdown_content + chunk,
          } : {
            markdown_content: chunk,
            structured_data: {},
          });
        },
        () => {
          setLoading(false);
          abortControllerRef.current = null;
        },
        (errorMsg) => {
          setError(errorMsg);
          setLoading(false);
          abortControllerRef.current = null;
        }
      );
    } catch (err: any) {
      console.error(err);
      setError(err.message || '发生错误，请重试');
      setLoading(false);
      abortControllerRef.current = null;
    }
  }, []);

  const resetAssessment = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setReport(null);
    setError(null);
    setStreamingContent('');
    setStreamingData(null);
  }, []);

  return {
    report,
    loading,
    error,
    streamingContent,
    streamingData,
    submitAssessment,
    resetAssessment
  };
};
