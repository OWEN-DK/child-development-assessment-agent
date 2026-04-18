import { useState, useEffect, useMemo } from 'react';
import { Form } from 'antd';
import { useNavigate } from 'react-router-dom';
import { getTestSet, getTestCases, addCasesToSet, removeCasesFromSet, runAllTests } from '@/api/rag-test';
import type { TestSet, TestCase } from '@/api/rag-test';
import { handleApiCall } from '@shared/lib/notification';

export function useTestSetDetail(id: string | undefined) {
  const navigate = useNavigate();
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
  const [form] = Form.useForm();

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
      onSuccess: (result) => {
        setRunModalVisible(false);
        if (result?.run_id) {
          navigate(`/rag-eval/runs/${result.run_id}`);
        }
      },
    });
  };

  const handleAddCases = async (values: { case_ids: string[] }) => {
    if (!id) return;
    await handleApiCall(() => addCasesToSet(id, values.case_ids), {
      successMsg: '添加成功',
      errorMsg: '添加失败',
      onSuccess: () => {
        setAddModalVisible(false);
        form.resetFields();
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

  const domains = useMemo(() => [...new Set(cases.map(c => c.domain))], [cases]);

  return {
    testSet,
    cases: filteredCases,
    availableCases,
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
      form,
    },
    actions: {
      handleRemoveCase,
      handleRunTest,
      handleAddCases,
    }
  };
}