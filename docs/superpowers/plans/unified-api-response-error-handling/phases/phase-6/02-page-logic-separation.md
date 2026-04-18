# Phase 6-2: 页面与逻辑分离

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `7.5.1` 节
> **所属 Phase**: Phase 6

## 需求定义

将所有 Page 组件的展示与逻辑分离，消除混合数据获取、过滤、渲染的超长组件。

## 验收标准

- [ ] 所有 Page 组件拆分为 hook + 展示组件 + 页面
- [ ] 单文件不超过 200 行
- [ ] 页面组件只负责组合
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| 所有 Page 组件 | 拆分 | hook + 展示组件 + 页面 |
| `features/*/hooks/` | 新增 | 业务逻辑 hooks |
| `features/*/components/` | 新增 | 展示组件 |

## 实现方案

### 拆分模式

**拆分前**（混合，217 行）：
```tsx
// RunListPage.tsx
const RunListPage = () => {
  const [loading, setLoading] = useState(false);
  const [runs, setRuns] = useState([]);
  
  // 数据获取（业务逻辑）
  useEffect(() => {
    setLoading(true);
    getTestRuns().then(setRuns).finally(() => setLoading(false));
  }, []);
  
  // 删除处理（业务逻辑）
  const handleDelete = async (id) => {
    await deleteTestRun(id);
    message.success('删除成功');
  };
  
  // 过滤计算（业务逻辑）
  const filteredRuns = runs.filter(r => r.status === statusFilter);
  
  // 列定义（UI 配置）
  const columns = [...];
  
  // JSX 渲染（展示）
  return <Table columns={columns} dataSource={filteredRuns} loading={loading} />;
};
```

**拆分后**：

```tsx
// features/rag-eval/hooks/useRunList.ts
export function useRunList() {
  const { data: runs, isLoading, mutate } = useQuery({
    queryKey: ['test-runs'],
    queryFn: getTestRuns,
  });
  
  const deleteRun = useMutation({
    mutationFn: deleteTestRun,
    onSuccess: () => {
      mutate();
      notification.success('删除成功');
    },
  });
  
  return { runs, isLoading, deleteRun: deleteRun.mutate };
}

// features/rag-eval/components/RunListTable.tsx
export const RunListTable = ({ runs, onDelete }: Props) => {
  const columns = [...]; // 列定义
  return <Table columns={columns} dataSource={runs} />;
};

// pages/rag-eval/run-list.tsx
export const RunListPage = () => {
  const { runs, isLoading, deleteRun } = useRunList();
  return <RunListTable runs={runs} loading={isLoading} onDelete={deleteRun} />;
};
```

### 拆分规则

| 文件 | 职责 | 行数限制 |
|------|------|---------|
| `hooks/useXxx.ts` | 数据获取、状态管理、业务逻辑 | ≤ 200 |
| `components/XxxTable.tsx` | 展示组件、列定义、UI 渲染 | ≤ 200 |
| `pages/xxx-list.tsx` | 组合 hook 和展示组件 | ≤ 50 |

## 测试方案

1. 拆分后页面展示与拆分前一致
2. hook 单元测试通过
3. 展示组件 Storybook 正常
4. 功能回归测试通过

## 注意事项

- 使用 React Query 管理服务端状态
- 展示组件应为纯函数（无副作用）
- 页面组件只负责组合，不包含业务逻辑
