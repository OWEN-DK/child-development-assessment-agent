/** 追踪系统 API 客户端 */

import { apiClient } from '@shared/api/client';
import type {
  Trace,
  TraceDetail,
  LLMCallLog,
  LLMCallLogDetail,
  PaginatedResponse,
  CostAnalysis,
  LatencyDistribution,
  ErrorAnalysis,
  TraceFilters,
} from '@entities/tracing/types';

export const tracingApi = {
  getTraces: async (
    page: number = 1,
    pageSize: number = 20,
    filters?: TraceFilters,
  ): Promise<PaginatedResponse<Trace>> => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('page_size', pageSize.toString());

    if (filters?.start_time) params.append('start_time', filters.start_time);
    if (filters?.end_time) params.append('end_time', filters.end_time);
    if (filters?.status) params.append('status', filters.status);
    if (filters?.user_id) params.append('user_id', filters.user_id);
    if (filters?.trace_id) params.append('trace_id', filters.trace_id);

    const res = await apiClient.get(`/api/v1/monitoring/traces?${params.toString()}`);
    return res.data;
  },

  getTraceDetail: async (traceId: string): Promise<TraceDetail> => {
    const res = await apiClient.get(`/api/v1/monitoring/traces/${traceId}`);
    return res.data;
  },

  getLLMCallLogs: async (
    page: number = 1,
    pageSize: number = 20,
    filters?: {
      trace_id?: string;
      model?: string;
      level?: string;
      start_time?: string;
      end_time?: string;
    },
  ): Promise<PaginatedResponse<LLMCallLog>> => {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('page_size', pageSize.toString());

    if (filters?.trace_id) params.append('trace_id', filters.trace_id);
    if (filters?.model) params.append('model', filters.model);
    if (filters?.level) params.append('level', filters.level);
    if (filters?.start_time) params.append('start_time', filters.start_time);
    if (filters?.end_time) params.append('end_time', filters.end_time);

    const res = await apiClient.get(`/api/v1/monitoring/logs?${params.toString()}`);
    return res.data;
  },

  getLLMCallLogDetail: async (requestId: string): Promise<LLMCallLogDetail> => {
    const res = await apiClient.get(`/api/v1/monitoring/logs/${requestId}`);
    return res.data;
  },

  getCostAnalysis: async (
    startTime?: string,
    endTime?: string,
  ): Promise<CostAnalysis> => {
    const params = new URLSearchParams();
    if (startTime) params.append('start_time', startTime);
    if (endTime) params.append('end_time', endTime);

    const res = await apiClient.get(`/api/v1/monitoring/cost?${params.toString()}`);
    return res.data;
  },

  getLatencyDistribution: async (
    startTime?: string,
    endTime?: string,
  ): Promise<LatencyDistribution> => {
    const params = new URLSearchParams();
    if (startTime) params.append('start_time', startTime);
    if (endTime) params.append('end_time', endTime);

    const res = await apiClient.get(`/api/v1/monitoring/latency?${params.toString()}`);
    return res.data;
  },

  getErrorAnalysis: async (
    startTime?: string,
    endTime?: string,
  ): Promise<ErrorAnalysis> => {
    const params = new URLSearchParams();
    if (startTime) params.append('start_time', startTime);
    if (endTime) params.append('end_time', endTime);

    const res = await apiClient.get(`/api/v1/monitoring/errors?${params.toString()}`);
    return res.data;
  },
};
