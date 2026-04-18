/**
 * 配置对比类型定义
 */

/** 配置对比数据 */
export interface ConfigComparison {
  param_name: string;
  param_name_zh?: string;
  current_version: string;
  current_value: unknown;
  suggested_value: unknown;
  safe_range?: [number, number];
  recommended_range?: [number, number];
  history_references: HistoryReference[];
}

/** 历史参考记录 */
export interface HistoryReference {
  version: string;
  changed_at: string;
  from_value: unknown;
  to_value: unknown;
  effect?: {
    p_at_5?: number;
    r_at_5?: number;
    [key: string]: number | undefined;
  };
}

/** 配置对比模态框属性 */
export interface ConfigComparisonModalProps {
  visible: boolean;
  paramName: string;
  currentVersion?: string;
  onClose: () => void;
}
