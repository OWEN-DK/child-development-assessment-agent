import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, beforeEach, expect, vi } from 'vitest';
import { ConfigForm } from '@/features/system-config/ConfigForm';

// Mock the chart components to avoid canvas issues in tests
vi.mock('@ant-design/charts', () => ({
  Line: () => <div data-testid="line-chart">Line Chart</div>,
  Pie: () => <div data-testid="pie-chart">Pie Chart</div>,
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

describe('Phase 7 前端集成测试', () => {
  beforeEach(() => {
    queryClient.clear();
  });

  describe('Schema 驱动配置表单', () => {
    it('配置表单渲染', async () => {
      render(
        <QueryClientProvider client={queryClient}>
          <ConfigForm />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('database')).toBeInTheDocument();
      });

      expect(screen.getByText('redis')).toBeInTheDocument();
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });
  });

  describe('LLM 监控仪表板', () => {
    it('仪表板渲染', async () => {
      const { LLMMonitoringDashboard } = await import('@/features/monitoring/LLMMonitoringDashboard');
      
      render(
        <QueryClientProvider client={queryClient}>
          <LLMMonitoringDashboard />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('LLM 监控仪表板')).toBeInTheDocument();
      });

      // 验证图表区域存在（数据加载时显示 skeleton）
      expect(screen.getByText('调用趋势')).toBeInTheDocument();
      expect(screen.getByText('模型使用分布')).toBeInTheDocument();
    });
  });
});