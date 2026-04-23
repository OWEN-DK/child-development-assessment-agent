import { useState, useEffect, useMemo } from 'react';

import { getTestSet, getTestCases, addCasesToSet, removeCasesFromSet, runAllTests } from '@/api/rag-test';
import type { TestSet, TestCase } from '@/api/rag-test';
import { handleApiCall } from '@shared/lib/notification';

export function useTestSetDetail(id: string | undefined) {

  const [testSet, setTestSet] = useState<TestSet | null>(null);
  const [cases, setCases] = useState<TestCase[]>([]);
  const [availableCases, setAvailableCases] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [keyword, setKeyword] = useState('');
  const [domainFilter, setDomainFilter] = useState<string | null>(null);

  // Modals state
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [runModalVisible, setRunModalVisible] = useState(false);
  const [runName, setRunName] = useState('');
  const [transferSelectedKeys, setTransferSelectedKeys] = useState<string[]>([]);

  useEffect(() => {
    if (!id) return;
    loadData();
  }, [id]);

  const loadData = async () => {
    if (!id) return;
    setLoading(true);
    await handleApiCall(async () => {
      const [set, allCases] = await Promise.all([getTestSet(id), getTestCases()]);
      setTestSet(set);
      const caseIds = new Set(set.test_case_ids || []);
      setCases(allCases.filter(c => caseIds.has(c.id)));
      setAvailableCases(allCases.filter(c => !caseIds.has(c.id)));
    }, {
      errorMsg: '加载失败',
    });
    setLoading(false);
  };

  const handleRemoveCase = async (caseId: string) => {
    if (!id) return;
    await handleApiCall(() => removeCasesFromSet(id, [caseId]), {
      successMsg: '已移除',
      errorMsg: '移除失败',
      onSuccess: () => loadData(),
    });
  };

  const handleRunTest = async () => {
    if (!id) return;
    await handleApiCall(() => runAllTests({ name: runName || `${testSet?.name}-运行`, test_set_ids: [id] }), {
      successMsg: '测试已启动',
      errorMsg: '启动失败',
      onSuccess: () => {
        setRunModalVisible(false);
        // 不跳转，留在当前页面，通过 SSE 推送进度
        // 用户可在运行列表页查看进度
      },
    });
  };

  const handleAddCases = async () => {
    if (!id || transferSelectedKeys.length === 0) return;
    await handleApiCall(() => addCasesToSet(id, transferSelectedKeys), {
      successMsg: `已添加 ${transferSelectedKeys.length} 个用例`,
      errorMsg: '添加失败',
      onSuccess: () => {
        setAddModalVisible(false);
        setTransferSelectedKeys([]);
        loadData();
      },
    });
  };

  const filteredCases = useMemo(() => {
    return cases.filter(c => {
      if (keyword && !c.query.toLowerCase().includes(keyword.toLowerCase())) return false;
      if (domainFilter && c.domain !== domainFilter) return false;
      return true;
    });
  }, [cases, keyword, domainFilter]);

  const filteredAvailableCases = useMemo(() => {
    return availableCases.filter(c => {
      if (keyword && !c.query.toLowerCase().includes(keyword.toLowerCase())) return false;
      if (domainFilter && c.domain !== domainFilter) return false;
      return true;
    });
  }, [availableCases, keyword, domainFilter]);

  const domains = useMemo(() => [...new Set(availableCases.map(c => c.domain))], [availableCases]);

  return {
    testSet,
    cases: filteredCases,
    availableCases: filteredAvailableCases,
    loading,
    domains,
    filters: {
      keyword,
      setKeyword,
      domainFilter,
      setDomainFilter,
    },
    modals: {
      addModalVisible,
      setAddModalVisible,
      runModalVisible,
      setRunModalVisible,
      runName,
      setRunName,
      transferSelectedKeys,
      setTransferSelectedKeys,
    },
    actions: {
      handleRemoveCase,
      handleRunTest,
      handleAddCases,
    }
  };
}