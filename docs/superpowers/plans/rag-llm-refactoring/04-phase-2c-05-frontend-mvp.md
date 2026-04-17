# Phase 2C.5: 前端集成 (MVP)

> **前置文档:** [Overview](./04-phase-2c-00-overview.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 1 人天

## 目标

实现前端调参建议面板，嵌入评估报告底部，**MVP 阶段仅展示规则引擎建议**。历史参考与 LLM 诊断面板移至后续迭代（Phase 2C 二期）。

> **⚠️ 范围约束**: 根据 Spec §8.7.2，MVP 阶段"仅展示规则引擎生成的 2-5 条核心建议"，"折叠展示历史参考（若有 ≥2 次历史运行）"为后续迭代项。本方案严格遵循此约束。

---

### Task 2C.5.1: 调参建议面板

**Files:**
- Create: `frontend/src/features/rag-evaluation/components/TuningSuggestionsPanel.tsx`
- Create: `frontend/src/features/rag-evaluation/api/tuning.ts`
- Modify: `frontend/src/features/rag-evaluation/components/EvaluationReport.tsx` (内嵌面板)

- [ ] **Step 1: 实现 API 客户端**

```typescript
// frontend/src/features/rag-evaluation/api/tuning.ts

export interface TuningSuggestion {
  param_name: string;
  current_value: any;
  suggested_value: any;
  action: string;
  reason: string;
  expected_effect: string;
  priority: "high" | "medium" | "low";
  source: string;
  safe_range?: [any, any];
}

export interface HistoryReference {
  run_id: string;
  date: string;
  changed_params: Record<string, { from: any; to: any }>;
  metric_changes: Record<string, { from: number; to: number; delta: string }>;
  conclusion: string;
}

export interface TuningSuggestionResponse {
  run_id: string;
  generated_at: string;
  rule_engine_suggestions: TuningSuggestion[];
  history_references: HistoryReference[];
  llm_diagnosis?: any;
  conflict_filtered_count: number;
  total_suggestions: number;
}

export const getTuningSuggestions = async (runId: string): Promise<TuningSuggestionResponse> => {
  const response = await fetch(`/api/v1/rag/test/run/${runId}/tuning-suggestions`);
  if (!response.ok) {
    throw new Error(`获取调参建议失败: ${response.statusText}`);
  }
  return response.json();
};

export const previewSuggestion = async (params: {
  run_id: string;
  param_name: string;
  suggested_value: number;
}): Promise<{ predicted_metrics?: Record<string, number>; based_on_history: boolean; message: string }> => {
  const response = await fetch("/api/v1/rag/test/tuning-suggestions/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return response.json();
};

export const applySuggestions = async (params: {
  run_id: string;
  suggestion_ids?: number[];
}): Promise<{ new_config_version_id: string; applied_params: Record<string, any> }> => {
  const response = await fetch("/api/v1/rag/test/tuning-suggestions/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return response.json();
};
```

- [ ] **Step 2: 实现调参建议面板组件**

```tsx
// frontend/src/features/rag-evaluation/components/TuningSuggestionsPanel.tsx
import React, { useEffect, useState } from "react";
import { Collapse, Card, Tag, Button, Spin, message } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined, CheckCircleOutlined } from "@ant-design/icons";
import { getTuningSuggestions, applySuggestions, TuningSuggestionResponse, TuningSuggestion } from "../api/tuning";

const { Panel } = Collapse;

interface TuningSuggestionsPanelProps {
  runId: string;
}

const priorityColor: Record<string, string> = {
  high: "red",
  medium: "orange",
  low: "blue",
};

const actionIcon: Record<string, React.ReactNode> = {
  increase: <ArrowUpOutlined style={{ color: "#52c41a" }} />,
  decrease: <ArrowDownOutlined style={{ color: "#ff4d4f" }} />,
  enable: <CheckCircleOutlined style={{ color: "#52c41a" }} />,
  disable: <CheckCircleOutlined style={{ color: "#ff4d4f" }} />,
};

export const TuningSuggestionsPanel: React.FC<TuningSuggestionsPanelProps> = ({ runId }) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<TuningSuggestionResponse | null>(null);

  useEffect(() => {
    loadSuggestions();
  }, [runId]);

  const loadSuggestions = async () => {
    setLoading(true);
    try {
      const result = await getTuningSuggestions(runId);
      setData(result);
    } catch (error) {
      message.error("获取调参建议失败");
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async (suggestion: TuningSuggestion) => {
    try {
      await applySuggestions({ run_id: runId });
      message.success("建议已应用，新配置版本已生成");
    } catch (error) {
      message.error("应用建议失败");
    }
  };

  if (loading) {
    return <Spin tip="正在生成调参建议..." />;
  }

  if (!data || data.total_suggestions === 0) {
    return null; // 无建议时不展示
  }

  return (
    <Card title="调参建议" style={{ marginTop: 24 }}>
      {data.conflict_filtered_count > 0 && (
        <div style={{ marginBottom: 12, color: "#999" }}>
          已过滤 {data.conflict_filtered_count} 条冲突建议
        </div>
      )}

      <Collapse defaultActiveKey={["rule-engine"]}>
        {/* 规则引擎建议 (MVP 唯一展示层) */}
        <Panel header={`快速建议 (${data.rule_engine_suggestions.length} 条)`} key="rule-engine">
          {data.rule_engine_suggestions.map((s, idx) => (
            <Card key={idx} size="small" style={{ marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <Tag color={priorityColor[s.priority]}>{s.priority === "high" ? "高" : s.priority === "medium" ? "中" : "低"}</Tag>
                  <strong>{s.param_name}</strong>
                  {actionIcon[s.action]}
                  <span style={{ marginLeft: 8 }}>
                    {s.current_value} → {s.suggested_value}
                  </span>
                </div>
                <Button size="small" onClick={() => handleApply(s)}>应用</Button>
              </div>
              <div style={{ marginTop: 8, color: "#666", fontSize: 12 }}>
                {s.expected_effect}
              </div>
            </Card>
          ))}
        </Panel>

        {/* ⏳ 历史参考面板 (Phase 2C 二期迭代，MVP 阶段不展示) */}
        {/* {data.history_references.length > 0 && ( ... )} */}
      </Collapse>
    </Card>
  );
};
```

- [ ] **Step 3: 嵌入评估报告**

```tsx
// frontend/src/features/rag-evaluation/components/EvaluationReport.tsx (修改)
import { TuningSuggestionsPanel } from "./TuningSuggestionsPanel";

// 在报告组件底部添加
export const EvaluationReport: React.FC<{ runId: string }> = ({ runId }) => {
  return (
    <div>
      {/* 原有报告内容 */}
      <ReportContent runId={runId} />
      
      {/* 调参建议面板 (MVP) */}
      <TuningSuggestionsPanel runId={runId} />
    </div>
  );
};
```

---

### Task 2C.5.2: 一键优化组件

**Files:**
- Create: `frontend/src/features/rag-evaluation/components/OneClickOptimize.tsx`

- [ ] **Step 1: 实现一键优化组件**

```tsx
// frontend/src/features/rag-evaluation/components/OneClickOptimize.tsx
import React, { useState } from "react";
import { Button, Radio, message, Modal } from "antd";
import { applySuggestions } from "../api/tuning";

interface OneClickOptimizeProps {
  runId: string;
}

export const OneClickOptimize: React.FC<OneClickOptimizeProps> = ({ runId }) => {
  const [loading, setLoading] = useState(false);
  const [target, setTarget] = useState("balanced"); // recall | precision | balanced

  const handleOptimize = async () => {
    Modal.confirm({
      title: "确认应用优化建议?",
      content: `优化目标: ${target === "recall" ? "召回优先" : target === "precision" ? "精度优先" : "平衡模式"}。此操作将创建新配置版本。`,
      onOk: async () => {
        setLoading(true);
        try {
          await applySuggestions({ run_id: runId });
          message.success("优化建议已应用");
        } catch (error) {
          message.error("应用失败");
        } finally {
          setLoading(false);
        }
      },
    });
  };

  return (
    <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
      <Radio.Group value={target} onChange={(e) => setTarget(e.target.value)}>
        <Radio.Button value="recall">召回优先</Radio.Button>
        <Radio.Button value="balanced">平衡模式</Radio.Button>
        <Radio.Button value="precision">精度优先</Radio.Button>
      </Radio.Group>
      <Button type="primary" loading={loading} onClick={handleOptimize}>
        一键优化
      </Button>
    </div>
  );
};
```

---

**上一阶段:** [统一引擎 + API](./04-phase-2c-04-engine-api.md)  
**下一阶段:** [TDD 测试策略](./04-phase-2c-06-testing.md)
