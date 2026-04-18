import React from 'react';
import { ConfigFieldMetadata } from '../../api/config/types';
import { useConfig } from '../../features/config/hooks/useConfig';
import { Switch, InputNumber, Input, Tooltip, Button, Select, Collapse } from 'antd';
import { notification } from '@shared/lib/notification';
import { QuestionCircleOutlined, WarningOutlined, PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';
import styles from './DynamicConfigForm.module.scss';

interface DynamicConfigFormProps {
  fields: ConfigFieldMetadata[];
  category?: string;
}

export const DynamicConfigForm: React.FC<DynamicConfigFormProps> = ({
  fields,
  category,
}) => {
  const { draftChanges, updateDraft } = useConfig();

  // 不常用字段列表（默认隐藏）
  const hiddenFields = [
    'frequency_penalty',
    'presence_penalty',
  ];

  // 需要独立展示的字段（不在场景配置中显示）
  const isolatedFields = [
    'llm_providers',
    'model_pricing',
  ];

  // 需要隐藏的旧字段（已被嵌套结构替代）
  const hiddenOldFields = [
    'model_report_generation',
    'model_assessment',
    'model_validation',
    'model_query_rewrite',
    'model_metadata_extraction',
    'model_vl_parsing',
    'model_query_classification',
    'ml_scoring_qwen_model',
  ];

  // 提供商选项
  const providerOptions = [
    { label: 'DashScope（阿里云百炼）', value: 'dashscope' },
    { label: 'OpenAI', value: 'openai' },
    { label: 'Anthropic', value: 'anthropic' },
    { label: 'DeepSeek', value: 'deepseek' },
    { label: 'Ollama（本地）', value: 'ollama' },
  ];

  // 场景详细说明
  const sceneDescriptions: Record<string, string> = {
    '报告生成': '用于生成儿童发展评估报告，包含评估结果、发展建议、训练计划等内容。建议使用高质量模型以保证报告的专业性和可读性。',
    '儿童评估': '核心评估节点，根据儿童画像和发展里程碑进行能力评估。需要较强的推理能力，建议使用高性能模型。',
    '结果校验': '对评估结果进行二次校验，确保评估结论的合理性和一致性。可使用中等性能模型以降低成本。',
    '查询重写': 'RAG 检索前对用户查询进行改写和扩展，提升检索准确率。需要理解语义，建议使用中等性能模型。',
    '元数据提取': '从上传的文档中提取标题、年龄段、发展领域等元数据信息。需要较强的文本理解能力。',
    '多模态解析': '解析图片、PDF 等多模态文档内容，提取文本信息。需要使用支持视觉理解的模型。',
    '查询分类': '对用户查询进行分类（如评估类、检索类、闲聊类），路由到不同的处理流程。可使用轻量级模型。',
    'ML 评分': '结合机器学习模型对 RAG 检索结果进行相关性评分。需要较强的判断能力。',
    '内容生成': '生成训练计划、活动建议等内容。需要创造性和专业性，建议使用高质量模型。',
  };

  // Group fields by category with support for nested categories (e.g., "rag.retrieval" -> RAG > Retrieval)
  // 修复：支持前缀匹配，选择父分类时显示所有子分类字段
  const filteredFields = category
    ? fields.filter((f) => f.category === category || f.category.startsWith(`${category}.`))
    : fields;

  // 过滤掉隐藏的旧字段
  const visibleFields = filteredFields.filter(f => !hiddenOldFields.includes(f.key));

  // 分离独立字段（凭证管理等）
  const isolatedFieldData = visibleFields.filter(f => isolatedFields.includes(f.key));
  const regularFields = visibleFields.filter(f => !isolatedFields.includes(f.key));
    
  const groupedFields = regularFields.reduce((groups, field) => {
    const fullCategory = field.category || '其他配置';
    // Split category by dot to support nested grouping
    const [mainCategory, subCategory] = fullCategory.split('.', 2);
    // Capitalize first letter for better display
    const formattedMainCategory = mainCategory.charAt(0).toUpperCase() + mainCategory.slice(1);
    
    if (!groups[formattedMainCategory]) {
      groups[formattedMainCategory] = {};
    }
    
    // 特殊处理 LLM 场景配置：按场景名称分组
    if (field.key.startsWith('llm_scene_configs__')) {
      const parts = field.key.split('__');
      if (parts.length >= 3) {
        const sceneName = parts[1]; // report_generation, assessment, etc.
        const sceneLabel = formatSceneName(sceneName);
        
        if (!groups[formattedMainCategory]['场景配置']) {
          groups[formattedMainCategory]['场景配置'] = {
            type: 'scene_configs',
            scenes: {}
          };
        }
        
        if (!groups[formattedMainCategory]['场景配置'].scenes[sceneLabel]) {
          groups[formattedMainCategory]['场景配置'].scenes[sceneLabel] = [];
        }
        
        groups[formattedMainCategory]['场景配置'].scenes[sceneLabel].push(field);
        return groups;
      }
    }
    
    const subGroup = subCategory 
      ? subCategory.charAt(0).toUpperCase() + subCategory.slice(1)
      : '通用配置';
      
    if (!groups[formattedMainCategory][subGroup]) {
      groups[formattedMainCategory][subGroup] = [];
    }
    
    groups[formattedMainCategory][subGroup].push(field);
    return groups;
  }, {} as Record<string, Record<string, any>>);

  // 格式化场景名称
  function formatSceneName(sceneName: string): string {
    const sceneLabels: Record<string, string> = {
      'report_generation': '报告生成',
      'assessment': '儿童评估',
      'validation': '结果校验',
      'query_rewrite': '查询重写',
      'metadata_extraction': '元数据提取',
      'vl_parsing': '多模态解析',
      'query_classification': '查询分类',
      'ml_scoring': 'ML 评分',
      'content_generation': '内容生成',
    };
    return sceneLabels[sceneName] || sceneName;
  }

  // 字段显示名称映射
  const fieldLabelMap: Record<string, string> = {
    'provider': '提供商',
    'model': '模型名称',
    'temperature': '温度参数',
    'max_tokens': '最大 Token 数',
    'top_p': 'Top-p 采样',
    'frequency_penalty': '频率惩罚',
    'presence_penalty': '存在惩罚',
    'api_key': 'API 密钥',
    'base_url': 'API 地址',
    'api_version': 'API 版本',
    'input_per_million': '输入价格（元/百万 Token）',
    'output_per_million': '输出价格（元/百万 Token）',
    'currency': '货币单位',
  };

  const renderField = (field: ConfigFieldMetadata) => {
    // 过滤不常用字段
    const fieldName = field.key.split('__').pop() || field.key;
    if (hiddenFields.includes(fieldName)) {
      return null;
    }

    const currentValue =
      draftChanges[field.key] ?? field.current_value;

    // 解析嵌套 key，提取显示标签
    const displayLabel = fieldLabelMap[fieldName] || fieldName;

    // 判断是否为嵌套配置项
    const isNested = field.key.includes('__');
    const nestingLevel = isNested ? field.key.split('__').length - 1 : 0;

    return (
      <div
        key={field.key}
        className={`${styles.configItem} ${isNested ? styles.nestedItem : ''}`}
        style={{ marginLeft: `${nestingLevel * 20}px` }}
      >
        <div className={styles.configHeader}>
          <div className={styles.configLabelGroup}>
            <span className={styles.configLabel}>
              {displayLabel}
            </span>
            <Tooltip title={field.description || '暂无描述'}>
              <QuestionCircleOutlined className={styles.helpIcon} />
            </Tooltip>
          </div>
          {field.requires_restart && (
            <Tooltip title="修改后需重启服务">
              <WarningOutlined className={styles.warningIcon} />
            </Tooltip>
          )}
        </div>

        <div className={styles.configControl}>
          {renderControl(field, currentValue, updateDraft, providerOptions)}
        </div>

        <div className={styles.configMeta}>
          <span>默认值: {String(field.default_value)}</span>
          {!field.hot_reloadable && (
            <span className={styles.coldUpdate}>冷更新</span>
          )}
        </div>
      </div>
    );
  };

  // 渲染凭证管理区域
  const renderCredentialSection = () => {
    const providersField = isolatedFieldData.find(f => f.key === 'llm_providers');
    if (!providersField) return null;

    const currentValue = draftChanges[providersField.key] ?? providersField.current_value;
    const dictValue = typeof currentValue === 'object' && currentValue !== null ? currentValue : {};

    // 校验：检查是否有重复的 provider
    const providers = Object.keys(dictValue);
    const hasDuplicate = providers.length !== new Set(providers).size;

    return (
      <div className={styles.mainCategory}>
        <h2 className={styles.mainCategoryTitle}>🔑 LLM 凭证管理</h2>
        <div className={styles.credentialGuide}>
          <p>配置各 LLM 提供商的 API 密钥和接口地址。每个提供商只能配置一个凭证。</p>
          {hasDuplicate && (
            <div className={styles.warningMessage}>
              ⚠️ 检测到重复的提供商配置，请删除重复项
            </div>
          )}
        </div>
        <div className={styles.categoryGrid}>
          {renderControl(providersField, currentValue, updateDraft, providerOptions)}
        </div>
      </div>
    );
  };

  // 渲染模型定价区域（可折叠，默认收起）
  const renderPricingSection = () => {
    const pricingField = isolatedFieldData.find(f => f.key === 'model_pricing');
    if (!pricingField) return null;

    const currentValue = draftChanges[pricingField.key] ?? pricingField.current_value;

    return (
      <div className={styles.mainCategory}>
        <Collapse
          defaultActiveKey={[]}
          items={[{
            key: '1',
            label: '💰 模型定价配置（用于成本统计）',
            children: (
              <div>
                <div className={styles.pricingGuide}>
                  <p>配置各模型的 Token 价格，用于计算 LLM 调用成本（单位：元/百万 Token）。</p>
                  <p>如不需要成本统计功能，可忽略此配置。</p>
                </div>
                <div className={styles.categoryGrid}>
                  {renderControl(pricingField, currentValue, updateDraft)}
                </div>
              </div>
            )
          }]}
        />
      </div>
    );
  };

  return (
    <div>
      {/* 配置说明 */}
      <div className={styles.configGuide}>
        <h3>💡 配置说明</h3>
        <ul>
          <li><strong>凭证管理</strong>：配置各 LLM 提供商的 API 密钥，每个提供商只能配置一个</li>
          <li><strong>场景配置</strong>：每个业务场景可独立选择提供商和模型参数</li>
          <li><strong>冷更新</strong>：标记为"冷更新"的配置项修改后需重启服务</li>
        </ul>
      </div>

      {/* 凭证管理区域（独立展示） */}
      {renderCredentialSection()}

      {/* 模型定价区域（可折叠） */}
      {renderPricingSection()}

      {/* 其他配置分类 */}
      {Object.entries(groupedFields).map(([mainCategory, subCategories]) => (
        <div key={mainCategory} className={styles.mainCategory}>
          <h2 className={styles.mainCategoryTitle}>{mainCategory}</h2>
          {Object.entries(subCategories as Record<string, any>).map(([subCategory, subData]) => {
            // 特殊处理场景配置
            if (subData.type === 'scene_configs') {
              return (
                <div key={subCategory} className={styles.subCategory}>
                  <h3 className={styles.subCategoryTitle}>{subCategory}</h3>
                  {Object.entries(subData.scenes).map(([sceneName, sceneFields]) => (
                    <div key={sceneName} className={styles.sceneConfigGroup}>
                      <div className={styles.sceneHeader}>
                        <div className={styles.sceneTitle}>{sceneName}</div>
                        {sceneDescriptions[sceneName] && (
                          <Tooltip title={sceneDescriptions[sceneName]}>
                            <QuestionCircleOutlined className={styles.sceneHelpIcon} />
                          </Tooltip>
                        )}
                      </div>
                      {sceneDescriptions[sceneName] && (
                        <div className={styles.sceneDescription}>{sceneDescriptions[sceneName]}</div>
                      )}
                      <div className={styles.sceneFields}>
                        {(sceneFields as ConfigFieldMetadata[]).map(renderField)}
                      </div>
                    </div>
                  ))}
                </div>
              );
            }
            
            // 普通配置分组
            return (
              <div key={subCategory} className={styles.subCategory}>
                <h3 className={styles.subCategoryTitle}>{subCategory}</h3>
                <div className={styles.categoryGrid}>
                  {(subData as ConfigFieldMetadata[]).map(renderField)}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};

function renderControl(
  field: ConfigFieldMetadata,
  value: any,
  onChange: (key: string, value: any) => void,
  providerOptions?: { label: string; value: string }[]
) {
  // 特殊处理 llm_providers 字段（凭证管理）
  if (field.key === 'llm_providers' && providerOptions) {
    const dictValue = typeof value === 'object' && value !== null ? value : {};

    return (
      <div className={styles.providerList}>
        {providerOptions.map((provider) => {
          const isConfigured = dictValue[provider.value];
          const config = isConfigured || { api_key: '', base_url: '', api_version: '' };

          return (
            <div key={provider.value} className={styles.providerCard}>
              <div className={styles.providerHeader}>
                <span className={styles.providerName}>{provider.label}</span>
                {isConfigured ? (
                  <Button
                    type="link"
                    danger
                    size="small"
                    onClick={() => {
                      const newDict = { ...dictValue };
                      delete newDict[provider.value];
                      onChange(field.key, newDict);
                    }}
                  >
                    移除
                  </Button>
                ) : (
                  <Button
                    type="link"
                    size="small"
                    onClick={() => {
                      const newDict = {
                        ...dictValue,
                        [provider.value]: { api_key: '', base_url: '', api_version: '' }
                      };
                      onChange(field.key, newDict);
                    }}
                  >
                    添加
                  </Button>
                )}
              </div>

              {isConfigured && (
                <div className={styles.providerFields}>
                  <div className={styles.fieldRow}>
                    <label>API Key:</label>
                    <Input.Password
                      value={config.api_key || ''}
                      onChange={(e) => {
                        const newDict = { ...dictValue };
                        newDict[provider.value] = { ...config, api_key: e.target.value };
                        onChange(field.key, newDict);
                      }}
                      placeholder="请输入 API Key"
                    />
                  </div>
                  <div className={styles.fieldRow}>
                    <label>Base URL:</label>
                    <Input
                      value={config.base_url || ''}
                      onChange={(e) => {
                        const newDict = { ...dictValue };
                        newDict[provider.value] = { ...config, base_url: e.target.value };
                        onChange(field.key, newDict);
                      }}
                      placeholder="可选，默认官方地址"
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  // 特殊处理 provider 字段（下拉框选择）
  const fieldName = field.key.split('__').pop() || field.key;
  if (fieldName === 'provider' && providerOptions) {
    return (
      <Select
        value={value}
        onChange={(val) => onChange(field.key, val)}
        options={providerOptions}
        style={{ width: '100%' }}
        size="middle"
        placeholder="选择提供商"
      />
    );
  }

  // 特殊处理 temperature 字段（0-2，步长 0.1）
  if (fieldName === 'temperature') {
    return (
      <InputNumber
        value={value}
        onChange={(val) => onChange(field.key, val)}
        min={0}
        max={2}
        step={0.1}
        style={{ width: '100%' }}
        size="middle"
        placeholder="0-2"
      />
    );
  }

  // 特殊处理 max_tokens 字段（1-32000，步长 100）
  if (fieldName === 'max_tokens') {
    return (
      <InputNumber
        value={value}
        onChange={(val) => onChange(field.key, val)}
        min={1}
        max={32000}
        step={100}
        style={{ width: '100%' }}
        size="middle"
        placeholder="1-32000"
      />
    );
  }

  // 特殊处理 top_p 字段（0-1，步长 0.05）
  if (fieldName === 'top_p') {
    return (
      <InputNumber
        value={value}
        onChange={(val) => onChange(field.key, val)}
        min={0}
        max={1}
        step={0.05}
        style={{ width: '100%' }}
        size="middle"
        placeholder="0-1"
      />
    );
  }

  // 特殊处理 frequency_penalty 字段（-2 到 2）
  if (fieldName === 'frequency_penalty') {
    return (
      <InputNumber
        value={value}
        onChange={(val) => onChange(field.key, val)}
        min={-2}
        max={2}
        step={0.1}
        style={{ width: '100%' }}
        size="middle"
        placeholder="-2 到 2"
      />
    );
  }

  // 特殊处理 presence_penalty 字段（-2 到 2）
  if (fieldName === 'presence_penalty') {
    return (
      <InputNumber
        value={value}
        onChange={(val) => onChange(field.key, val)}
        min={-2}
        max={2}
        step={0.1}
        style={{ width: '100%' }}
        size="middle"
        placeholder="-2 到 2"
      />
    );
  }

  // Handle dictionary/object types
  if (field.type === 'dict' || field.type === 'Dict') {
    const dictValue = typeof value === 'object' && value !== null && !Array.isArray(value) ? value : {};
    
    // Check if all values are primitive types (string, number, boolean)
    const isSimpleDict = Object.values(dictValue).every(val => 
      typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean'
    );

    // Check if values are nested objects (like llm_providers or model_pricing)
    const isNestedDict = Object.values(dictValue).some(val =>
      typeof val === 'object' && val !== null && !Array.isArray(val)
    );
    
    if (isSimpleDict) {
      return (
        <div className={styles.dictEditor}>
          {Object.entries(dictValue).map(([key, val], index) => (
            <div key={index} className={styles.itemRow}>
              <Input
                value={key}
                placeholder="键名"
                onChange={(e) => {
                  const newDict = { ...dictValue };
                  const oldKey = Object.keys(dictValue)[index];
                  const newKey = e.target.value;
                  if (newKey && newKey !== oldKey) {
                    delete newDict[oldKey];
                    newDict[newKey] = val;
                    onChange(field.key, newDict);
                  }
                }}
                style={{ width: '35%' }}
                size="middle"
              />
              <Input
                value={String(val)}
                placeholder="值"
                onChange={(e) => {
                  const newDict = { ...dictValue };
                  const currentKey = Object.keys(dictValue)[index];
                  let newValue: any = e.target.value;
                  // Try to convert to number
                  if (!isNaN(Number(newValue)) && newValue.trim() !== '') {
                    newValue = Number(newValue);
                  } else if (newValue.toLowerCase() === 'true') {
                    newValue = true;
                  } else if (newValue.toLowerCase() === 'false') {
                    newValue = false;
                  }
                  newDict[currentKey] = newValue;
                  onChange(field.key, newDict);
                }}
                style={{ flex: 1 }}
                size="middle"
              />
              <MinusCircleOutlined
                onClick={() => {
                  const newDict = { ...dictValue };
                  const currentKey = Object.keys(dictValue)[index];
                  delete newDict[currentKey];
                  onChange(field.key, newDict);
                }}
                className={styles.deleteIcon}
              />
            </div>
          ))}
          <Button
            type="dashed"
            onClick={() => {
              onChange(field.key, { ...dictValue, 'new_key': '' });
            }}
            icon={<PlusOutlined />}
            style={{ width: '100%' }}
            size="middle"
          >
            添加键值对
          </Button>
        </div>
      );
    }

    // Handle nested dictionaries (like llm_providers, model_pricing)
    if (isNestedDict) {
      // 特殊处理 llm_providers：使用下拉框选择提供商，防止重复
      const isProvidersField = field.key === 'llm_providers';
      const existingProviders = Object.keys(dictValue);
      const availableProviders = providerOptions?.filter(
        opt => !existingProviders.includes(opt.value)
      ) || [];

      return (
        <div className={styles.nestedDictEditor}>
          {Object.entries(dictValue).map(([key, val]) => (
            <div key={key} className={styles.nestedDictItem}>
              <div className={styles.nestedDictKey}>
                {isProvidersField ? (
                  <Select
                    value={key}
                    disabled
                    options={providerOptions}
                    size="small"
                    style={{ width: '100%' }}
                  />
                ) : (
                  key
                )}
              </div>
              <div className={styles.nestedDictValue}>
                {Object.entries(val as Record<string, any>).map(([subKey, subVal]) => (
                  <div key={subKey} className={styles.nestedDictRow}>
                    <span className={styles.nestedDictSubKey}>{subKey}:</span>
                    {subKey === 'provider' && providerOptions ? (
                      <Select
                        value={subVal}
                        onChange={(newVal) => {
                          const newDict = { ...dictValue };
                          const newValObj = { ...(newDict[key] as Record<string, any>) };
                          newValObj[subKey] = newVal;
                          newDict[key] = newValObj;
                          onChange(field.key, newDict);
                        }}
                        options={providerOptions}
                        size="small"
                        style={{ flex: 1 }}
                        placeholder="选择提供商"
                      />
                    ) : (
                      <Input
                        value={String(subVal ?? '')}
                        onChange={(e) => {
                          const newDict = { ...dictValue };
                          const newValObj = { ...(newDict[key] as Record<string, any>) };
                          let parsedVal: any = e.target.value;
                          if (!isNaN(Number(parsedVal)) && parsedVal.trim() !== '') {
                            parsedVal = Number(parsedVal);
                          } else if (parsedVal.toLowerCase() === 'true') {
                            parsedVal = true;
                          } else if (parsedVal.toLowerCase() === 'false') {
                            parsedVal = false;
                          } else if (parsedVal === '' || parsedVal.toLowerCase() === 'null') {
                            parsedVal = null;
                          }
                          newValObj[subKey] = parsedVal;
                          newDict[key] = newValObj;
                          onChange(field.key, newDict);
                        }}
                        size="small"
                        style={{ flex: 1 }}
                        type={subKey === 'api_key' ? 'password' : 'text'}
                      />
                    )}
                  </div>
                ))}
                <Button
                  type="link"
                  danger
                  size="small"
                  onClick={() => {
                    const newDict = { ...dictValue };
                    delete newDict[key];
                    onChange(field.key, newDict);
                  }}
                  style={{ marginTop: 8, padding: 0 }}
                >
                  删除此提供商
                </Button>
              </div>
            </div>
          ))}
          {isProvidersField && availableProviders.length > 0 && (
            <Button
              type="dashed"
              onClick={() => {
                const newProvider = availableProviders[0];
                const newDict = {
                  ...dictValue,
                  [newProvider.value]: {
                    provider: newProvider.value,
                    api_key: '',
                    base_url: null,
                    api_version: null,
                  }
                };
                onChange(field.key, newDict);
              }}
              icon={<PlusOutlined />}
              style={{ width: '100%' }}
              size="middle"
            >
              添加提供商
            </Button>
          )}
          {isProvidersField && availableProviders.length === 0 && existingProviders.length > 0 && (
            <div className={styles.allProvidersAdded}>
              ✅ 所有提供商已配置
            </div>
          )}
        </div>
      );
    }
    
    // Fallback to JSON editor for complex objects
    return (
      <Input.TextArea
        value={JSON.stringify(value, null, 2)}
        onChange={(e) => {
          try {
            const parsedValue = JSON.parse(e.target.value);
            onChange(field.key, parsedValue);
          } catch (err) {
            notification.error('JSON格式不正确，请检查');
          }
        }}
        rows={6}
        style={{ width: '100%', fontFamily: 'monospace' }}
      />
    );
  }

  // Handle string list/array types with dynamic add/remove editor
  if (field.type === 'list' || field.type === 'List') {
    const listValue = Array.isArray(value) ? value : [];
    
    // Check if all items are strings
    const isStringList = listValue.every(item => typeof item === 'string');
    
    if (isStringList) {
      return (
        <div className={styles.listEditor}>
          {listValue.map((item, index) => (
            <div key={index} className={styles.itemRow}>
              <Input
                value={item}
                onChange={(e) => {
                  const newList = [...listValue];
                  newList[index] = e.target.value;
                  onChange(field.key, newList);
                }}
                style={{ flex: 1 }}
                size="middle"
              />
              <MinusCircleOutlined
                onClick={() => {
                  const newList = listValue.filter((_, i) => i !== index);
                  onChange(field.key, newList);
                }}
                className={styles.deleteIcon}
              />
            </div>
          ))}
          <Button
            type="dashed"
            onClick={() => {
              onChange(field.key, [...listValue, '']);
            }}
            icon={<PlusOutlined />}
            style={{ width: '100%' }}
            size="middle"
          >
            添加项
          </Button>
        </div>
      );
    }
    
    // Fallback to JSON editor for non-string lists
    return (
      <Input.TextArea
        value={JSON.stringify(value, null, 2)}
        onChange={(e) => {
          try {
            const parsedValue = JSON.parse(e.target.value);
            onChange(field.key, parsedValue);
          } catch (err) {
            notification.error('JSON格式不正确，请检查');
          }
        }}
        rows={6}
        style={{ width: '100%', fontFamily: 'monospace' }}
      />
    );
  }

  switch (field.type) {
    case 'bool':
      return (
        <Switch
          checked={!!value}
          onChange={(checked) => onChange(field.key, checked)}
        />
      );
    case 'float':
      return (
        <InputNumber
          value={value}
          onChange={(val) => onChange(field.key, val)}
          step={0.05}
          style={{ width: '100%' }}
          size="middle"
        />
      );
    case 'int':
      return (
        <InputNumber
          value={value}
          onChange={(val) => onChange(field.key, val)}
          step={1}
          style={{ width: '100%' }}
          size="middle"
        />
      );
    case 'str':
      return (
        <Input
          value={value}
          onChange={(e) => onChange(field.key, e.target.value)}
        />
      );
    default:
      // Try to handle complex types as JSON
      if (typeof value === 'object' && value !== null) {
        return (
          <Input.TextArea
            value={JSON.stringify(value, null, 2)}
            onChange={(e) => {
              try {
                const parsedValue = JSON.parse(e.target.value);
                onChange(field.key, parsedValue);
              } catch (err) {
                notification.error('JSON格式不正确，请检查');
              }
            }}
            rows={4}
            style={{ width: '100%', fontFamily: 'monospace' }}
          />
        );
      }
      return (
        <Input
          value={String(value ?? '')}
          onChange={(e) => onChange(field.key, e.target.value)}
        />
      );
  }
}
