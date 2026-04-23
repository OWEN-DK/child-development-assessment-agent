import { useState, useEffect, useCallback, useRef } from 'react';
import dayjs from 'dayjs';
import { getTestRuns, batchDeleteTestRuns, getTestSets, runAllTests, cancelTestRun } from '@/api/rag-test';
import type { TestRun, TestSet } from '@/api/rag-test';
import { handleApiCall, notification } from '@shared/lib/notification';
import { API_BASE_URL } from '@shared/lib/constants';

export interface RunTask {
  taskId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  message: string;
  createdAt: number;
  name?: string;
  totalTestCases?: number;
  error?: string;
}

interface SSEConnection {
  eventSource: EventSource;
  taskId: string;
}

function buildSSEUrl(taskId: string): string {
  const base = API_BASE_URL.replace(/\/$/, '');
  return `${base}/api/v1/tasks/test_run/${taskId}/stream`;
}

const ACTIVE_STATUS_FILTER = ['pending', 'running'] as const;

export function useRunManagement() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningTasks, setRunningTasks] = useState<RunTask[]>([]);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [testSetFilter, setTestSetFilter] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  
  const sseConnectionsRef = useRef<Map<string, SSEConnection>>(new Map());
  const callbacksRef = useRef({ loadData: () => {} });
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    await handleApiCall(async () => {
      const [runsData, setsData] = await Promise.all([getTestRuns(), getTestSets()]);
      setRuns(runsData);
      setTestSets(setsData);
    }, {
      errorMsg: '加载失败',
    });
    setLoading(false);
  }, []);

  useEffect(() => {
    callbacksRef.current = { loadData };
  }, [loadData]);

  const closeSSE = useCallback((taskId: string) => {
    const conn = sseConnectionsRef.current.get(taskId);
    if (conn) {
      conn.eventSource.close();
      sseConnectionsRef.current.delete(taskId);
    }
  }, []);

  const connectSSE = useCallback((taskId: string) => {
    if (sseConnectionsRef.current.has(taskId)) {
      return;
    }

    const url = buildSSEUrl(taskId);
    const es = new EventSource(url);
    sseConnectionsRef.current.set(taskId, { eventSource: es, taskId });

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const eventType = data.type || data.event || 'message';

        setRunningTasks(prev => {
          const taskIndex = prev.findIndex(t => t.taskId === taskId);
          if (taskIndex === -1) {
            return prev;
          }

          const updatedTasks = [...prev];
          const task = { ...updatedTasks[taskIndex] };

          if (eventType === 'progress') {
            task.status = data.status || 'running';
            task.progress = data.progress ?? task.progress;
            task.message = data.message || task.message;
            updatedTasks[taskIndex] = task;
          } else if (eventType === 'complete') {
            const { loadData: ld } = callbacksRef.current;
            if (data.status === 'completed') {
              notification.success(`${task.name || '测试运行'} 已完成`);
              ld();
            } else if (data.status === 'cancelled') {
              notification.info(`${task.name || '测试运行'} 已取消`);
              ld();
            }
            closeSSE(taskId);
            return prev.filter(t => t.taskId !== taskId);
          } else if (eventType === 'error') {
            closeSSE(taskId);
            notification.error(`${task.name || '测试运行'} 失败：${data.error || '未知错误'}`);
            return prev.filter(t => t.taskId !== taskId);
          }

          return updatedTasks;
        });

        // 同步更新运行历史列表中的对应记录
        if (eventType === 'progress') {
          setRuns(prev => {
            const runIndex = prev.findIndex(r => r.id === taskId);
            if (runIndex === -1) return prev;
            
            const updatedRuns = [...prev];
            const run = { ...updatedRuns[runIndex] };
            
            // 根据 SSE 数据更新运行记录
            run.status = data.status || 'running';
            if (data.progress !== undefined) {
              // 假设 total_test_cases 已知，计算 passed_test_cases
              if (run.total_test_cases) {
                run.passed_test_cases = Math.round((data.progress / 100) * run.total_test_cases);
              }
            }
            
            updatedRuns[runIndex] = run;
            return updatedRuns;
          });
        }
      } catch (e) {
        console.error('SSE message parse failed:', e);
      }
    };

    es.onerror = () => {
      console.error(`SSE connection error for task ${taskId}`);
      es.close();
      sseConnectionsRef.current.delete(taskId);
    };
  }, [closeSSE]);

  const loadTasks = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/tasks/active?task_type=test_run`);
      if (!response.ok) return;
      
      const data = await response.json();
      const tasks = data.data?.tasks || [];
      
      const activeTasks: RunTask[] = tasks
        .filter((t: any) => ACTIVE_STATUS_FILTER.includes(t.status))
        .map((t: any) => ({
          taskId: t.task_id,
          status: t.status,
          progress: t.progress || 0,
          message: t.message || '等待执行',
          createdAt: t.created_at || Date.now(),
          name: t.metadata?.name,
          totalTestCases: t.metadata?.total_test_cases,
        }));

      setRunningTasks(activeTasks);

      activeTasks.forEach(task => {
        if (task.status === 'pending' || task.status === 'running') {
          connectSSE(task.taskId);
        }
      });

      const hasRunningTasks = activeTasks.some(t => 
        t.status === 'pending' || t.status === 'running'
      );
      
      if (hasRunningTasks && !pollingIntervalRef.current) {
        pollingIntervalRef.current = setInterval(async () => {
          try {
            const res = await fetch(`${API_BASE_URL}/api/v1/tasks/active?task_type=test_run`);
            if (!res.ok) return;
            const data = await res.json();
            const tasks = data.data?.tasks || [];
            const activeTasks: RunTask[] = tasks
              .filter((t: any) => ACTIVE_STATUS_FILTER.includes(t.status))
              .map((t: any) => ({
                taskId: t.task_id,
                status: t.status,
                progress: t.progress || 0,
                message: t.message || '等待执行',
                createdAt: t.created_at || Date.now(),
                name: t.metadata?.name,
                totalTestCases: t.metadata?.total_test_cases,
              }));
            setRunningTasks(activeTasks);
          } catch (e) {
            console.error('Polling failed:', e);
          }
        }, 5000);
      } else if (!hasRunningTasks && pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    } catch (e) {
      console.error('Failed to load tasks:', e);
    }
  }, [connectSSE]);

  const handleDelete = async (id: string) => {
    await handleApiCall(() => batchDeleteTestRuns([id]), {
      successMsg: '删除成功',
      errorMsg: '删除失败',
      onSuccess: () => loadData(),
    });
  };

  const handleCancel = async (taskId: string) => {
    try {
      await cancelTestRun(taskId);
      closeSSE(taskId);
      setRunningTasks(prev => prev.filter(t => t.taskId !== taskId));
      notification.info('已请求取消任务');
    } catch (e) {
      console.error('Cancel failed:', e);
      notification.error('取消失败');
    }
  };

  const handleRunTest = async (data?: { name?: string; test_set_ids?: string[] }) => {
    await handleApiCall(() => runAllTests(data), {
      successMsg: '测试已启动',
      errorMsg: '启动失败',
      onSuccess: (result) => {
        if (result?.run_id) {
          const newTask: RunTask = {
            taskId: result.run_id,
            status: 'pending',
            progress: 0,
            message: '等待执行',
            createdAt: Date.now(),
            name: data?.name,
          };
          setRunningTasks(prev => [...prev, newTask]);
          connectSSE(result.run_id);
          loadData();
        }
      },
    });
  };

  const addTask = useCallback((task: RunTask) => {
    setRunningTasks(prev => {
      const exists = prev.find(t => t.taskId === task.taskId);
      if (exists) {
        return prev.map(t => t.taskId === task.taskId ? task : t);
      }
      return [...prev, task];
    });

    if (task.status === 'pending' || task.status === 'running') {
      connectSSE(task.taskId);
    }
  }, [connectSSE]);

  useEffect(() => {
    loadData();
    loadTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => {
      sseConnectionsRef.current.forEach(conn => {
        conn.eventSource.close();
      });
      sseConnectionsRef.current.clear();
      
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, []);

  const filteredRuns = runs.filter(r => {
    if (statusFilter && r.status !== statusFilter) return false;
    if (testSetFilter && r.test_set_id !== testSetFilter) return false;
    if (dateRange) {
      const runDate = dayjs(r.created_at);
      if (runDate.isBefore(dateRange[0]) || runDate.isAfter(dateRange[1])) return false;
    }
    return true;
  });

  return {
    runs: filteredRuns,
    testSets,
    loading,
    runningTasks,
    filters: {
      statusFilter,
      setStatusFilter,
      testSetFilter,
      setTestSetFilter,
      dateRange,
      setDateRange,
    },
    actions: {
      handleDelete,
      handleCancel,
      handleRunTest,
      loadData,
      addTask,
    }
  };
}
