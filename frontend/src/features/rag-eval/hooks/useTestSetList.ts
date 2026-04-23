import { useState, useEffect } from 'react';
import { useTestSetStore, type SourceType } from '../hooks/useTestSetStore';
import { handleApiCall } from '@shared/lib/notification';

export interface CreateFormValues {
  name: string;
  description?: string;
  source_type?: SourceType;
}

export function useTestSetList() {
  const store = useTestSetStore();
  const [createModalVisible, setCreateModalVisible] = useState(false);

  useEffect(() => {
    store.fetchTestSets();
  }, []);

  const handleCreate = async (values: CreateFormValues, resetForm: () => void) => {
    await handleApiCall(() => store.createTestSet(values), {
      successMsg: '创建成功',
      errorMsg: '创建失败',
      onSuccess: () => {
        setCreateModalVisible(false);
        resetForm();
      }
    });
  };

  const handleDelete = async (id: string) => {
    await handleApiCall(() => store.deleteTestSet(id), {
      successMsg: '删除成功',
      errorMsg: '删除失败',
    });
  };

  const handleBatchDelete = async (ids: string[]) => {
    await handleApiCall(() => store.batchDeleteTestSets(ids), {
      successMsg: `已删除 ${ids.length} 个测试集`,
      errorMsg: '批量删除失败',
    });
  };

  return {
    ...store,
    createModalVisible,
    setCreateModalVisible,
    handleCreate,
    handleDelete,
    handleBatchDelete,
  };
}