import { configApi } from '@/api/config';
import { calculateLocalScore } from './scoringService';

export interface DiagnosticSuggestion {
  priority: 'high' | 'medium' | 'low';
  issue: string;
  suggestion: string;
  config_path: string;
  current_value: string;
  recommended_value: string;
}

export interface DiagnosticResult {
  score: number;
  score_basis: string;
  suggestions: DiagnosticSuggestion[];
  cached_at?: string;
}

let healthDiagnosticTimer: NodeJS.Timeout | null = null;

export class DiagnosticService {
  static async runDiagnostic(
    currentConfig: Record<string, any>,
    cachedDiagnostic: DiagnosticResult | null
  ): Promise<DiagnosticResult> {
    // 检查缓存（5 分钟有效期）
    if (cachedDiagnostic?.cached_at) {
      const cachedTime = new Date(cachedDiagnostic.cached_at).getTime();
      const now = Date.now();
      if (now - cachedTime < 5 * 60 * 1000) {
        return cachedDiagnostic;
      }
    }

    try {
      const result = await configApi.runHealthDiagnostic({ config: currentConfig });
      return {
        ...result,
        cached_at: new Date().toISOString()
      };
    } catch (error) {
      console.warn('健康诊断 API 调用失败，使用本地规则评分:', error);
      return calculateLocalScore(currentConfig);
    }
  }

  static scheduleDiagnostic(
    currentConfig: Record<string, any>,
    cachedDiagnostic: DiagnosticResult | null,
    onResult: (result: DiagnosticResult) => void,
    onStart: () => void
  ) {
    if (healthDiagnosticTimer) {
      clearTimeout(healthDiagnosticTimer);
    }
    
    healthDiagnosticTimer = setTimeout(async () => {
      onStart();
      const result = await this.runDiagnostic(currentConfig, cachedDiagnostic);
      onResult(result);
    }, 30000); // 30 秒防抖
  }
}