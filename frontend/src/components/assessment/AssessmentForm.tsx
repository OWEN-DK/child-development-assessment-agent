import React from 'react';
import {
  ProForm,
  ProFormText,
  ProFormDigit,
  ProFormSelect,
  ProFormList,
  ProFormGroup,
  ProCard,
  ProFormDatePicker,
} from '@ant-design/pro-components';
import type { UserInput } from '@entities/assessment/types';
import { useAssessmentForm } from '../../features/assessment/hooks/useAssessmentForm';
import styles from './AssessmentForm.module.scss';

interface AssessmentFormProps {
  onSubmit: (data: UserInput) => Promise<void>;
  isLoading: boolean;
}

export const AssessmentForm: React.FC<AssessmentFormProps> = ({ onSubmit, isLoading }) => {
  const { initialValues, handleFinish } = useAssessmentForm();

  return (
    <div className={styles.assessmentForm}>
      <ProForm<UserInput>
        onFinish={(values) => handleFinish(values, onSubmit)}
        submitter={{
          searchConfig: {
            submitText: isLoading ? '正在评估中...' : '开始评估',
          },
          submitButtonProps: {
            loading: isLoading,
            size: 'large',
            style: { width: '100%' },
          },
          resetButtonProps: {
            style: { display: 'none' },
          },
        }}
        initialValues={initialValues}
        layout="vertical"
      >
        <ProCard title="1. 儿童基本画像" headerBordered className="ant-pro-card">
          <ProFormGroup>
            <ProFormText
              name={['child_profile', 'name']}
              label="姓名"
              placeholder="如：小明"
              width="md"
              rules={[{ required: true, message: '请输入姓名' }]}
            />
            <ProFormDigit
              name={['child_profile', 'age']}
              label="年龄 (岁)"
              min={0}
              max={18}
              width="sm"
              rules={[{ required: true, message: '请输入年龄' }]}
            />
            <ProFormSelect
              name={['child_profile', 'gender']}
              label="性别"
              width="sm"
              options={[
                { label: '男', value: 'male' },
                { label: '女', value: 'female' },
                { label: '其他', value: 'other' },
              ]}
              rules={[{ required: true, message: '请选择性别' }]}
            />
          </ProFormGroup>

          <ProFormSelect
            name={['child_profile', 'issues']}
            label="主要问题 / 症状"
            placeholder="例如：注意力不集中, 怕高"
            mode="tags"
            fieldProps={{
              tokenSeparators: [',', '，', '\n']
            }}
            rules={[{ required: false }]}
          />

          <ProFormSelect
            name={['child_profile', 'interests']}
            label="兴趣爱好"
            placeholder="例如：乐高, 恐龙"
            mode="tags"
            fieldProps={{
              tokenSeparators: [',', '，', '\n']
            }}
            rules={[{ required: false }]}
          />
        </ProCard>

        <ProCard title="2. 拟定训练计划" headerBordered className="ant-pro-card">
          <ProFormText
            name={['proposed_plan', 'plan_name']}
            label="计划名称"
            placeholder="例如：感统强化计划 A"
            rules={[{ required: true, message: '请输入计划名称' }]}
          />

          <ProFormSelect
            name={['proposed_plan', 'goals']}
            label="计划目标"
            placeholder="例如：提升前庭平衡, 增强核心力量"
            mode="tags"
            fieldProps={{
              tokenSeparators: [',', '，', '\n']
            }}
            rules={[{ required: false }]}
          />

          <ProFormList
            name={['proposed_plan', 'activities']}
            label="活动列表"
            creatorButtonProps={{
              position: 'bottom',
              creatorButtonText: '添加新活动',
            }}
            itemRender={({ listDom, action }, { record }) => {
              return (
                <ProCard
                  extra={action}
                  title={record?.name || '新活动'}
                  style={{ marginBottom: 8 }}
                >
                  {listDom}
                </ProCard>
              );
            }}
          >
            <ProFormGroup>
              <ProFormText
                name="name"
                label="活动名称"
                placeholder="例如：拍球"
                rules={[{ required: true }]}
                width="md"
              />
              <ProFormDigit
                name="duration_minutes"
                label="时长 (分钟)"
                min={1}
                rules={[{ required: true }]}
                width="xs"
              />
              <ProFormDigit
                name="frequency_weekly"
                label="每周频次"
                min={1}
                rules={[{ required: true }]}
                width="xs"
              />
              <ProFormSelect
                name="intensity"
                label="强度"
                width="xs"
                options={[
                  { label: '低', value: 'low' },
                  { label: '中', value: 'medium' },
                  { label: '高', value: 'high' },
                ]}
              />
            </ProFormGroup>
            <ProFormText
              name="description"
              label="描述/备注"
              placeholder="具体的动作要求..."
            />
          </ProFormList>
        </ProCard>
        <ProCard title="3. 历史运动记录 (可选)" headerBordered className="ant-pro-card" collapsible defaultCollapsed>
          <ProFormList
            name={['history_context']}
            label="历史记录列表"
            creatorButtonProps={{
              position: 'bottom',
              creatorButtonText: '添加日期记录',
            }}
            itemRender={({ listDom, action }, { record }) => {
              return (
                <ProCard
                  extra={action}
                  title={record?.date || '新记录'}
                  style={{ marginBottom: 8 }}
                >
                  {listDom}
                </ProCard>
              );
            }}
          >
            <ProFormGroup>
              <ProFormDatePicker
                name="date"
                label="日期"
                width="md"
                rules={[{ required: true, message: '请选择日期' }]}
              />
              <ProFormText
                name="notes"
                label="当日备注"
                placeholder="整体感受..."
                width="md"
              />
            </ProFormGroup>
            
            <ProFormList
              name="activities"
              label="当日活动"
              creatorButtonProps={{
                creatorButtonText: '添加活动',
              }}
              itemRender={({ listDom, action }, {}) => {
                return (
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8, gap: 8 }}>
                    <div style={{ flex: 1 }}>{listDom}</div>
                    {action}
                  </div>
                );
              }}
            >
              <ProFormGroup>
                <ProFormText
                  name="name"
                  label="活动名称"
                  placeholder="例如：跑步"
                  width="sm"
                  rules={[{ required: true, message: '请输入名称' }]}
                />
                <ProFormDigit
                  name="duration_minutes"
                  label="时长(分)"
                  width="xs"
                  min={1}
                  rules={[{ required: true, message: '请输入时长' }]}
                />
                <ProFormSelect
                  name="intensity"
                  label="强度"
                  width="xs"
                  options={[
                    { label: '低', value: 'low' },
                    { label: '中', value: 'medium' },
                    { label: '高', value: 'high' },
                  ]}
                />
                <ProFormText
                  name="feedback"
                  label="反馈/感受"
                  placeholder="例如：很累"
                  width="sm"
                />
              </ProFormGroup>
            </ProFormList>
          </ProFormList>
        </ProCard>
      </ProForm>
    </div>
  );
};
