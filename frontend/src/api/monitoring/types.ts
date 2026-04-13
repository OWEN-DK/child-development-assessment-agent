export interface MonitoringStatistics {
  total_calls: number;
  error_rate: number;
  total_tokens: number;
  avg_duration_ms: number;
}

export interface TrendItem {
  hour: string;
  value: number;
}

export interface MonitoringTrend {
  trend: TrendItem[];
}

export interface ModelDistributionItem {
  model_name: string;
  count: number;
}

export interface ModelDistribution {
  distribution: ModelDistributionItem[];
}