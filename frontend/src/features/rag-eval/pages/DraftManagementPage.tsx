/**
 * 草稿管理页
 * 路由: /rag-eval (Tab: 草稿管理)
 *
 * 工作流约束：
 * - 数据来源：书籍上传 / JSON 导入
 * - 允许操作：✅ 上传书籍  ✅ 导入 JSON  ✅ 审核草稿  ✅ 编辑草稿
 * - 禁止操作：❌ 直接创建测试用例
 */

import { useState, useEffect, useRef } from 'react';
import {
  Table,
  Tag,
  Button,
  Space,
  Select,
  Input,
  Popconfirm,
  Typography,
  Spin,
  Modal,
  Card,
} from 'antd';
import { notification } from '@shared/lib/notification';
import apiClient from '@shared/api/client';
import {
  CheckOutlined,
  CloseOutlined,
  UploadOutlined,
  ImportOutlined,
  SearchOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import type { TestCaseDraft } from '@/entities/test-case/types';
import { getDrafts, reviewDraft, batchDeleteDrafts } from '@/api/rag-test';
import DraftDetailModal from '../components/DraftDetailModal';
import DraftCreateForm from '../components/DraftCreateForm';
import UploadWithGeneration from '../components/UploadWithGeneration';
import { ProgressList } from '@/components/progress';
import { draftGenerationConfig, type DraftGenerationTask } from '@/components/progress/configs/draftGeneration';
import type { TaskStatus } from '@/components/progress/types';
import styles from './DraftManagementPage.module.scss';

const { Title } = Typography;

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: '待审核', color: 'orange' },
  reviewed: { label: '已通过', color: 'green' },
  rejected: { label: '已拒绝', color: 'red' },
  imported: { label: '已归入', color: 'blue' },
};

export default function DraftManagementPage() {
  const [drafts, setDrafts] = useState<TestCaseDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('draft');
  const [keyword, setKeyword] = useState('');
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [createModalVisible, setCreateModalVisible] = useState(false);

  // 上传相关
  const [uploadModalVisible, setUploadModalVisible] = useState(false);

  // JSON 导入相关
  const [importing, setImporting] = useState(false);

  // 草稿生成任务列表
  const [draftTasks, setDraftTasks] = useState<DraftGenerationTask[]>([]);
  const activeTaskIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    loadData();
    // 启动轮询检查活跃任务
    const pollInterval = setInterval(() => {
      checkActiveTasks();
    }, 2000);
    return () => clearInterval(pollInterval);
  }, []);

  // 检查活跃任务
  const checkActiveTasks = async () => {
    if (activeTaskIdsRef.current.size === 0) return;
    
    try {
      const response = await apiClient.get('/rag/test/drafts/generate/tasks');
      const tasks = response.data?.tasks || [];
      
      const newTasks: DraftGenerationTask[] = [];
      const completedIds: string[] = [];
      
       const statusMap: Record<string, TaskStatus> = {
         processing: 'running',
         success: 'completed',
         failed: 'failed',
         cancelled: 'cancelled',
       };

       tasks.forEach((task: any) => {
         if (activeTaskIdsRef.current.has(task.task_id)) {
           // 转换任务格式
           const draftTask: DraftGenerationTask = {
             taskId: task.task_id,
             status: statusMap[task.status] || 'running',
             progress: task.progress || 0,
             message: task.message || '草稿生成中',
             createdAt: task.created_at || Date.now(),
             domain: task.domain || '未知领域',
             ageStage: task.age_stage || '未知年龄段',
             generated: task.generated,
             deduplicated: task.deduplicated,
             totalCombinations: task.total_combinations,
             currentCombination: task.current_combination,
           };
           newTasks.push(draftTask);
          
          // 如果任务已完成，从活跃集合中移除
          if (task.status === 'success' || task.status === 'failed' || task.status === 'cancelled') {
            completedIds.push(task.task_id);
          }
        }
      });
      
      // 清理已完成的任务
      completedIds.forEach(id => activeTaskIdsRef.current.delete(id));
      
      setDraftTasks(newTasks);
      
      // 如果有任务完成，刷新草稿列表
      if (completedIds.length > 0) {
        setTimeout(() => loadData(), 1000);
      }
    } catch (error) {
      console.error('Failed to check active tasks:', error);
    }
  };

  // 添加新任务到监听列表
  const addDraftTask = (taskId: string, domain?: string, ageStage?: string) => {
    activeTaskIdsRef.current.add(taskId);
    
    // 立即添加一个占位任务
    const newTask: DraftGenerationTask = {
      taskId,
      status: 'running',
      progress: 0,
      message: '草稿生成中',
      createdAt: Date.now(),
      domain: domain || '未知领域',
      ageStage: ageStage || '未知年龄段',
    };
    
    setDraftTasks(prev => [...prev, newTask]);
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const draftsData = await getDrafts();
      setDrafts(draftsData);
    } catch {
      notification.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (draftId: string, action: 'reviewed' | 'rejected') => {
    try {
      await reviewDraft(draftId, action);
      notification.success(action === 'reviewed' ? '已通过' : '已拒绝');
      loadData();
    } catch {
      notification.error('操作失败');
    }
  };

  const handleBatchApprove = async () => {
    if (selectedRowKeys.length === 0) return;
    try {
      for (const key of selectedRowKeys) {
        await reviewDraft(key as string, 'reviewed');
      }
      notification.success('批量归入成功');
      setSelectedRowKeys([]);
      loadData();
    } catch {
      notification.error('批量归入失败');
    }
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) return;
    try {
      await batchDeleteDrafts(selectedRowKeys as string[]);
      notification.success(`已删除 ${selectedRowKeys.length} 个草稿`);
      setSelectedRowKeys([]);
      loadData();
    } catch {
      notification.error('批量删除失败');
    }
  };

  // 手动生成草稿（暂未使用）
  // const [generatingDrafts, setGeneratingDrafts] = useState(false);
  // const handleGenerateDrafts = async (docId: string) => {
  //   if (!docId) {
  //     message.warning('请先选择源文档');
  //     return;
  //   }
  //   
  //   setGeneratingDrafts(true);
  //   try {
  //     const params: GenerationParams = {
  //       target_domains: ['感觉统合'],
  //       age_range: [0, 6],
  //       count: 10,
  //       difficulty: 'medium',
  //       llm_model: 'qwen-turbo',
  //       temperature: 0.7,
  //     };
  //
  //     const response = await generateDrafts(docId, params);
  //     
  //     if (response.task_id) {
  //       notification.success('已开始生成草稿');
  //       startListeningDraftProgress(response.task_id);
  //     }
  //   } catch {
  //     notification.error('生成草稿失败');
  //   } finally {
  //     setGeneratingDrafts(false);
  //   }
  // };

  // JSON 导入
  const handleJsonImport = async () => {
    setImporting(true);
    try {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.json';
      input.onchange = async (e) => {
        const file = (e.target as HTMLInputElement).files?.[0];
        if (!file) return;

        const content = await file.text();
        const importData = JSON.parse(content);

        // 预览
        const formData = new FormData();
        formData.append('file', new Blob([content], { type: 'application/json' }), file.name);

        const previewRes = await apiClient.post('/rag/test/cases/import/preview', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });

        const { valid_cases } = previewRes.data;

        if (valid_cases.length === 0) {
          notification.error('没有有效的测试用例');
          return;
        }

        // 批量导入
        await apiClient.post('/rag/test/cases/batch', {
          cases: importData,
        });

        notification.success(`成功导入 ${valid_cases.length} 个用例`);
        loadData();
      };
      input.click();
    } catch {
      notification.error('导入失败');
    } finally {
      setImporting(false);
    }
  };

  const filteredDrafts = drafts.filter(d => {
    if (statusFilter && d.status !== statusFilter) return false;
    if (keyword && !d.query.toLowerCase().includes(keyword.toLowerCase())) return false;
    return true;
  });

  const pendingCount = drafts.filter(d => d.status === 'draft').length;

  const DOMAIN_MAP: Record<string, string> = {
    sensory_integration: '感觉统合',
    gross_motor: '粗大动作',
    fine_motor: '精细动作',
    language: '语言发展',
    cognitive: '认知能力',
    social_emotional: '社交情感',
  };

  const columns = [
    {
      title: '查询语句',
      dataIndex: 'query',
      key: 'query',
      width: 300,
      ellipsis: true,
      render: (text: string, record: { id: string }) => (
        <a onClick={() => { setSelectedDraftId(record.id); setDetailModalVisible(true); }}>{text}</a>
      ),
    },
    {
      title: '来源文档',
      dataIndex: 'source_document_name',
      key: 'source_document_name',
      width: 120,
      ellipsis: true,
      render: (name: string) => name || '-',
    },
    {
      title: '年龄',
      dataIndex: 'age',
      key: 'age',
      width: 90,
      render: (age: number) => {
        if (!age && age !== 0) return '-';
        const years = Math.floor(age / 12);
        const months = age % 12;
        if (years > 0 && months > 0) return `${years}岁${months}月`;
        if (years > 0) return `${years}岁`;
        return `${months}月`;
      },
    },
    {
      title: '领域',
      dataIndex: 'domain',
      key: 'domain',
      width: 100,
      render: (domain: string) => DOMAIN_MAP[domain] || domain,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={STATUS_MAP[status]?.color}>{STATUS_MAP[status]?.label || status}</Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: { id: string; status: string }) => {
        const isDraft = record.status === 'draft';
        return (
          <Space>
            {isDraft && (
              <>
                <Popconfirm title="通过此草稿？" onConfirm={() => handleReview(record.id, 'reviewed')}>
                  <Button type="link" size="small" icon={<CheckOutlined />}>通过</Button>
                </Popconfirm>
                <Popconfirm title="拒绝此草稿？" onConfirm={() => handleReview(record.id, 'rejected')}>
                  <Button type="link" size="small" danger icon={<CloseOutlined />}>拒绝</Button>
                </Popconfirm>
              </>
            )}
            {!isDraft && '-'}
          </Space>
        );
      },
    },
  ];

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div className={styles.container}>
      <Card className={styles.headerCard}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Title level={3} style={{ marginBottom: 16 }}>草稿管理</Title>
            <Space wrap>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)}>
                新增草稿
              </Button>
              <Button icon={<UploadOutlined />} onClick={() => setUploadModalVisible(true)}>
                上传书籍并生成
              </Button>
              <Button icon={<ImportOutlined />} onClick={handleJsonImport} loading={importing}>
                导入 JSON
              </Button>
            </Space>
          </div>

          <div className={styles.filterBar}>
            <Space wrap>
              <Input
                placeholder="搜索查询语句"
                prefix={<SearchOutlined />}
                style={{ width: 240 }}
                value={keyword}
                onChange={e => setKeyword(e.target.value)}
                allowClear
              />
              <Select
                value={statusFilter}
                onChange={setStatusFilter}
                style={{ width: 140 }}
                options={[
                  { label: '待审核', value: 'draft' },
                  { label: '已通过', value: 'reviewed' },
                  { label: '已拒绝', value: 'rejected' },
                  { label: '已归入', value: 'imported' },
                ]}
              />
              <Tag color="orange">待审核: {pendingCount}</Tag>
              <Tag>总数: {drafts.length}</Tag>
            </Space>
            {selectedRowKeys.length > 0 && (
              <Space>
                <Popconfirm title={`批量通过 ${selectedRowKeys.length} 个草稿？`} onConfirm={handleBatchApprove}>
                  <Button type="primary">
                    批量归入 ({selectedRowKeys.length})
                  </Button>
                </Popconfirm>
                <Popconfirm title={`确认删除 ${selectedRowKeys.length} 个草稿？`} onConfirm={handleBatchDelete}>
                  <Button danger>
                    批量删除 ({selectedRowKeys.length})
                  </Button>
                </Popconfirm>
              </Space>
            )}
          </div>

          <ProgressList<DraftGenerationTask>
            config={{
              ...draftGenerationConfig,
              onCancel: async (task) => {
                try {
                  await apiClient.post(`/rag/test/drafts/generate/${task.taskId}/cancel`);
                  setDraftTasks(prev => prev.filter(t => t.taskId !== task.taskId));
                  activeTaskIdsRef.current.delete(task.taskId);
                  notification.info('已请求取消任务');
                } catch (error) {
                  notification.error('取消失败');
                }
              },
            }}
            tasks={draftTasks}
          />
        </Space>
      </Card>

      <Card
        title="草稿列表"
        className={styles.listCard}
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={loadData}
            loading={loading}
            size="small"
          >
            刷新
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={filteredDrafts}
          rowKey="id"
          rowSelection={{
            selectedRowKeys,
            onChange: keys => setSelectedRowKeys(keys),
            getCheckboxProps: record => ({ disabled: record.status !== 'draft' }),
          }}
          scroll={{ x: 1200 }}
          pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
          locale={{ emptyText: '暂无草稿，请先上传书籍或导入 JSON' }}
        />
      </Card>

      <Modal
        title="上传书籍并生成草稿"
        open={uploadModalVisible}
        onCancel={() => { setUploadModalVisible(false); }}
        footer={null}
        width={700}
        closable={false}
      >
        <UploadWithGeneration
          onSuccess={(taskId: string) => {
            setUploadModalVisible(false);
            loadData();
            addDraftTask(taskId);
          }}
          onCancel={() => { setUploadModalVisible(false); }}
        />
      </Modal>

      <DraftDetailModal
        visible={detailModalVisible}
        draftId={selectedDraftId}
        onClose={() => { setDetailModalVisible(false); setSelectedDraftId(null); }}
        onReview={handleReview}
      />

      <DraftCreateForm
        visible={createModalVisible}
        onClose={() => setCreateModalVisible(false)}
        onSuccess={() => { setCreateModalVisible(false); loadData(); }}
      />
    </div>
  );
}
