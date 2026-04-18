import type { DiagnosticResult } from './diagnosticService';

export function calculateLocalScore(config: Record<string, any>): DiagnosticResult {
  let score = 0;

  // LLM 凭证 (30%)
  const llmProviders = config.llm_providers || {};
  if (Object.keys(llmProviders).length > 0) score += 30;

  // 核心场景模型 (25%)
  const sceneConfigs = config.llm_scene_configs || {};
  const recommendedModels = ['qwen-max', 'qwen-plus'];
  const hasRecommendedModel = Object.values(sceneConfigs).some(
    (sc: any) => recommendedModels.includes(sc?.model)
  );
  if (hasRecommendedModel) score += 25;

  // RAG 配置 (20%)
  const ragRetrieval = config.rag_retrieval || {};
  if (ragRetrieval.strategy && ragRetrieval.chunk_size) score += 20;

  // 业务规则 (15%)
  const rules = config.rules || {};
  if (Object.keys(rules).length > 0) score += 15;

  // 系统设置 (10%)
  const system = config.system || {};
  if (system.logging && system.paths) score += 10;

  return {
    score,
    score_basis: '基于本地规则评分（降级模式）',
    suggestions: []
  };
}