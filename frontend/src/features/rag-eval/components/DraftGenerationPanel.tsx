/**
 * 草稿生成面板组件
 * 支持文档选择、多维度矩阵生成、实时预估、高级设置、SSE 进度展示
 */

import { useState, useEffect, useCallback } from 'react';
import { Form, Checkbox, InputNumber, Button, Collapse, Radio, Select, App } from 'antd';
import { estimateDraftGeneration, getDraftConfig, getAvailableModels, generateDrafts, getSourceDocuments } from '@/api/rag-test';
import type { GenerationParams, EstimateResult, SourceDocument } from '@/entities/test-case/types';

const { Panel } = Collapse;

interface DraftGenerationPanelProps {
  onSuccess: (taskId: string) => void;
}

export default function DraftGenerationPanel({ onSuccess }: DraftGenerationPanelProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [estimate, setEstimate] = useState<EstimateResult | null>(null);
  const [availableModels, setAvailableModels] = useState<Array<{ key: string; name: string; cost_input: number; cost_output: number }>>([]);
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  
  // 动态配置选项
  const [domainOptions, setDomainOptions] = useState<string[]>([]);
  const [ageStageOptions, setAgeStageOptions] = useState<string[]>([]);
  const [queryTypeOptions, setQueryTypeOptions] = useState<string[]>([]);
  const [difficultyOptions, setDifficultyOptions] = useState<string[]>([]);

  // 加载已上传的文档列表
  useEffect(() => {
    const loadDocuments = async () => {
      try {
        const docs = await getSourceDocuments();
        setDocuments(docs);
        if (docs.length > 0) {
          setSelectedDocId(docs[0].id);
        }
      } catch {
        message.warning('无法加载文档列表');
      }
    };
    loadDocuments();
  }, []);

  // 加载系统默认配置
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await getDraftConfig();
        
        // 设置选项列表
        const domains = config.supported_domains || ['粗大动作', '精细动作', '语言发展', '认知能力', '社交情感', '感觉统合'];
        const ageStages = (config.age_stages || []).map((s: any) => s.label);
        setDomainOptions(domains);
        setAgeStageOptions(ageStages);
        setQueryTypeOptions((config.query_types || []).map((t: any) => t.name));
        setDifficultyOptions((config.difficulty_levels || []).map((d: any) => d.name));
        
        // 设置表单默认值（领域和年龄段默认全选）
        form.setFieldsValue({
          domains: config.default_domains || domains,
          age_stages: config.default_age_stages || ageStages,
          drafts_per_combination: config.default_drafts_per_combination || 3,
          query_types: config.default_query_types || ['事实性查询', '比较性查询', '方案性查询'],
          difficulty_levels: config.default_difficulty_levels || ['入门级', '中级', '高级'],
          model: config.default_model || 'qwen-plus',
          deduplication_threshold: config.deduplication_threshold || 0.85,
          combination_interval_seconds: config.combination_interval_seconds || 1,
          mode: 'append',
        });
      } catch {
        // 加载失败时使用兜底值
        const fallbackDomains = ['粗大动作', '精细动作', '语言发展', '认知能力', '社交情感', '感觉统合'];
        const fallbackAgeStages = ['0-1岁', '1-3岁', '3-6岁', '6-9岁', '9-12岁', '12-15岁', '15-18岁'];
        setDomainOptions(fallbackDomains);
        setAgeStageOptions(fallbackAgeStages);
        setQueryTypeOptions(['事实性查询', '比较性查询', '方案性查询', '原因分析性查询']);
        setDifficultyOptions(['入门级', '中级', '高级']);
        
        // 领域和年龄段默认全选
        form.setFieldsValue({
          domains: fallbackDomains,
          age_stages: fallbackAgeStages,
          drafts_per_combination: 3,
          query_types: ['事实性查询', '比较性查询', '方案性查询'],
          difficulty_levels: ['入门级', '中级', '高级'],
          model: 'qwen-plus',
          deduplication_threshold: 0.85,
          combination_interval_seconds: 1,
          mode: 'append',
        });
      }
    };
    loadConfig();
  }, [form]);

  // 加载可用模型列表
  useEffect(() => {
    const loadModels = async () => {
      try {
        const models = await getAvailableModels();
        setAvailableModels(models);
      } catch {
        setAvailableModels([]);
      }
    };
    loadModels();
  }, []);

  // 实时预估
  const handleValuesChange = useCallback(async () => {
    if (!selectedDocId) return;
    const values = form.getFieldsValue();
    if (values.domains?.length && values.age_stages?.length && values.drafts_per_combination) {
      try {
        const result = await estimateDraftGeneration(selectedDocId, {
          target_domains: values.domains,
          age_stages: values.age_stages,
          drafts_per_combination: values.drafts_per_combination,
          llm_model: values.model || 'qwen-plus',
        } as GenerationParams);
        
        // 计算预估成本
        const selectedModel = availableModels.find(m => m.key === (values.model || 'qwen-plus'));
        if (selectedModel && result.total_drafts > 0) {
          // 假设每个草稿约 1000 token 输入 + 500 token 输出
          const inputTokens = result.total_drafts * 1000;
          const outputTokens = result.total_drafts * 500;
          const inputCost = (inputTokens / 1000000) * selectedModel.cost_input;
          const outputCost = (outputTokens / 1000000) * selectedModel.cost_output;
          (result as EstimateResult).estimated_cost = inputCost + outputCost;
        }
        
        setEstimate(result);
      } catch {
        // 预估失败不影响表单
      }
    }
  }, [form, selectedDocId, availableModels]);

  // 提交生成
  const handleSubmit = async () => {
    if (!selectedDocId) {
      message.warning('请先选择一个文档');
      return;
    }
    const values = form.getFieldsValue();
    if (!values.domains?.length) {
      message.warning('请至少选择一个领域');
      return;
    }
    if (!values.age_stages?.length) {
      message.warning('请至少选择一个年龄段');
      return;
    }

    setLoading(true);
    try {
      const result = await generateDrafts(selectedDocId, {
        target_domains: values.domains,
        age_stages: values.age_stages,
        drafts_per_combination: values.drafts_per_combination,
        query_types: values.query_types || ['事实性查询', '比较性查询', '方案性查询'],
        difficulty_levels: values.difficulty_levels || ['入门级', '中级', '高级'],
        llm_model: values.model || 'qwen-plus',
        temperature: 0.8,
        mode: values.mode || 'append',
      } as GenerationParams);

      message.success(`生成任务已启动，任务 ID: ${result.task_id}`);
      onSuccess(result.task_id);
    } catch (error: any) {
      message.error(error.message || '启动生成任务失败');
    } finally {
      setLoading(false);
    }
  };

  if (documents.length === 0) {
    return (
      <div style={{ padding: '40px 0', textAlign: 'center', color: '#999' }}>
        <p>暂无已上传的文档，请先上传书籍</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '16px 0' }}>
      <Form form={form} onValuesChange={handleValuesChange} layout="vertical">
        {/* 文档选择 */}
        <Form.Item label="选择源文档" required>
          <Select
            value={selectedDocId}
            onChange={setSelectedDocId}
            placeholder="请选择要生成草稿的文档"
            options={documents.map(doc => ({
              label: doc.title || doc.id,
              value: doc.id,
            }))}
          />
        </Form.Item>

        {/* 主面板 */}
        <Form.Item name="domains" label="选择发展领域（可多选）" rules={[{ required: true, message: '请至少选择一个领域' }]}>
          <Checkbox.Group options={domainOptions} />
        </Form.Item>

        <Form.Item name="age_stages" label="选择年龄段（可多选）" rules={[{ required: true, message: '请至少选择一个年龄段' }]}>
          <Checkbox.Group options={ageStageOptions} />
        </Form.Item>

        <Form.Item name="drafts_per_combination" label="每个组合生成数量" rules={[{ required: true, message: '请输入草稿数' }]}>
          <InputNumber min={1} max={10} style={{ width: 120 }} />
        </Form.Item>

        {/* 预估信息 */}
        {estimate && (
          <div style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, marginBottom: 16 }}>
            <h4 style={{ margin: '0 0 8px 0' }}>📊 预估信息</h4>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              <li>选中领域：{estimate.domains.length} 个</li>
              <li>选中年龄段：{estimate.age_stages.length} 个</li>
              <li>组合数量：{estimate.combinations} 个（{estimate.domains.length}×{estimate.age_stages.length}）</li>
              <li>每个组合草稿数：{estimate.drafts_per_combination} 个</li>
              <li>预计生成：{estimate.total_drafts} 个草稿</li>
              {estimate.estimated_cost !== undefined && (
                <li>预估成本：¥{estimate.estimated_cost.toFixed(2)}</li>
              )}
            </ul>
          </div>
        )}

        <Form.Item>
          <Button type="primary" onClick={handleSubmit} loading={loading} style={{ marginRight: 8 }}>
            开始生成
          </Button>
        </Form.Item>

        {/* 高级设置 */}
        <Collapse>
          <Panel header="高级设置" key="advanced">
            <Form.Item name="model" label="模型选择">
              <Select
                options={availableModels.map(m => ({
                  label: `${m.name}（输入¥${m.cost_input}/百万，输出¥${m.cost_output}/百万）`,
                  value: m.key,
                }))}
                placeholder={availableModels.length === 0 ? '请先在系统配置中设置模型成本' : '请选择模型'}
              />
            </Form.Item>

            <Form.Item name="query_types" label="查询类型">
              <Checkbox.Group options={queryTypeOptions} />
            </Form.Item>

            <Form.Item name="difficulty_levels" label="难度级别">
              <Checkbox.Group options={difficultyOptions} />
            </Form.Item>

            <Form.Item name="deduplication_threshold" label="去重阈值">
              <InputNumber min={0.7} max={0.95} step={0.05} style={{ width: 120 }} />
            </Form.Item>

            <Form.Item name="combination_interval_seconds" label="组合间隔（秒）">
              <InputNumber min={0} max={5} step={0.5} style={{ width: 120 }} />
            </Form.Item>

            <Form.Item name="mode" label="生成模式">
              <Radio.Group>
                <Radio value="append">追加</Radio>
                <Radio value="overwrite">覆盖</Radio>
              </Radio.Group>
            </Form.Item>
          </Panel>
        </Collapse>
      </Form>
    </div>
  );
}
