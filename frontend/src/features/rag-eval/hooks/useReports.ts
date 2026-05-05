import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { message } from 'antd';
import * as reportsApi from '@/api/rag-eval/reports';
import { downloadBlob } from '@/features/rag-eval/utils/export';

/** 报告列表筛选参数 */
export interface ReportFilters {
  page?: number;
  page_size?: number;
  run_id?: string;
}

/** 获取报告列表 */
export function useReports(filters?: ReportFilters) {
  return useQuery({
    queryKey: ['rag-eval', 'reports', filters],
    queryFn: () => reportsApi.getReports(filters),
    staleTime: 30_000,
  });
}

/** 获取单个报告详情 */
export function useReport(id: string) {
  return useQuery({
    queryKey: ['rag-eval', 'reports', id],
    queryFn: () => reportsApi.getReport(id),
    staleTime: 60_000,
    enabled: !!id,
  });
}

/** 为指定运行生成评估报告 */
export function useGenerateReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => reportsApi.generateReport(runId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'reports'] });
    },
  });
}

/** 删除单个报告 */
export function useDeleteReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reportsApi.deleteReport(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'reports'] });
    },
  });
}

/** 批量删除报告 */
export function useBatchDeleteReports() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) => reportsApi.batchDeleteReports(ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rag-eval', 'reports'] });
    },
  });
}

/** 导出报告（JSON / CSV / PDF） */
export function useExportReport() {
  return useMutation({
    mutationFn: (params: { reportId: string; format: 'json' | 'csv' | 'pdf' }) =>
      reportsApi.exportReport(params.reportId, params.format),
    onSuccess: (blob, variables) => {
      const ext = variables.format;
      downloadBlob(blob, `report-${variables.reportId}.${ext}`);
      message.success('导出成功');
    },
    onError: () => {
      message.error('导出失败');
    },
  });
}

/** 获取指定指标的最近趋势数据 */
export function useTrends(metric: string, limit: number = 10) {
  return useQuery({
    queryKey: ['rag-eval', 'trends', metric, limit],
    queryFn: () => reportsApi.getTrends({ limit }),
    staleTime: 120_000,
    enabled: !!metric,
  });
}
