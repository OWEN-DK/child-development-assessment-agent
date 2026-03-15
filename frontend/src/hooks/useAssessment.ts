import { useState, useCallback, useRef } from 'react';
import { UserInput, FinalReport, StreamingReportData } from '../models';
import { assessDevelopment, assessDevelopmentStream } from '../api/client';

export const useAssessment = () => {
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

    // 取消之前的流式请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    if (!useStreaming) {
      // 非流式模式
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
      return;
    }

    // 流式模式
    try {
      abortControllerRef.current = new AbortController();

      await assessDevelopmentStream(
        data,
        (data) => {
          // 收到结构化数据
          setStreamingData(data);
          setReport({
            markdown_content: '',
            structured_data: data,
          });
        },
        (chunk) => {
          // 收到内容片段，逐字追加
          setStreamingContent((prev) => prev + chunk);
          setReport((prev) => prev ? {
            ...prev,
            markdown_content: prev.markdown_content + chunk,
          } : {
            markdown_content: chunk,
            structured_data: {},
          });
        },
        () => {
          // 流式生成完成
          setLoading(false);
          abortControllerRef.current = null;
        },
        (errorMsg) => {
          // 发生错误
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
    // 取消正在进行的流式请求
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
