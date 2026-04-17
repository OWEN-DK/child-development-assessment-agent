# Phase 4.1: P0 Bug 修复

> **优先级:** P0（阻塞性，必须首先修复）
> **预估工作量:** 2-3 小时

---

## 🎯 目标

修复 3 个阻塞性 Bug，确保系统配置页面基础功能正常：
1. `/api/v1/config/reset` 端点缺失
2. 保存 API 字段名不匹配
3. 分类过滤逻辑缺陷

---

## 🐛 Bug 1: 恢复出厂设置端点缺失

### 问题描述
前端 `configStore.ts` 第 113 行调用 `configApi.resetToFactory()` 请求 `/api/v1/config/reset`，但后端 `config_controller.py` 中没有任何 `/reset` 路由。

### 影响
点击"恢复出厂设置"按钮必然 404。

### 修复方案

#### 1. 后端新增 `/reset` 路由

**文件:** `backend/src/controller/config_controller.py`

```python
@router.post("/reset")
async def reset_to_factory(
    request: ResetConfigRequest,
    current_user: User = Depends(get_current_user)
):
    """恢复出厂设置"""
    try:
        # 1. 获取出厂配置（从 .env.dev 或硬编码默认值）
        factory_config = await config_manager.get_factory_config()
        
        # 2. 保存为新版本（记录审计日志）
        version = await config_manager.save_config(
            config_snapshot=factory_config,
            description="恢复出厂设置",
            created_by=current_user.id,
            is_factory_reset=True
        )
        
        return {
            "success": True,
            "version_id": version.id,
            "message": "已恢复出厂设置"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 2. 新增请求 Schema

**文件:** `backend/src/schemas/config.py`

```python
class ResetConfigRequest(BaseModel):
    """恢复出厂设置请求"""
    confirm: bool = Field(..., description="二次确认标志")
    reason: Optional[str] = Field(None, description="恢复原因")
```

#### 3. ConfigManager 新增方法

**文件:** `backend/src/config/core/manager.py`

```python
async def get_factory_config(self) -> dict:
    """获取出厂默认配置"""
    # 从 .env.dev 或硬编码默认值加载
    # 返回完整的配置快照
    pass
```

#### 4. 前端二次确认

**文件:** `frontend/src/store/configStore.ts`

```typescript
resetToFactory: async () => {
  // 显示二次确认对话框
  const confirmed = await showConfirmDialog({
    title: '确认恢复出厂设置？',
    content: '此操作将清除所有自定义配置，是否继续？',
    okText: '确认恢复',
    cancelText: '取消',
    okButtonProps: { danger: true }
  });
  
  if (!confirmed) return;
  
  await configApi.resetToFactory({ confirm: true });
  // 重新加载配置
  await get().loadConfig();
}
```

### 测试

**文件:** `backend/tests/api/test_config_reset.py`

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_reset_to_factory_success(client: TestClient, mock_user):
    """测试恢复出厂设置成功"""
    with patch('src.controller.config_controller.config_manager') as mock_manager:
        # Mock 出厂配置
        mock_manager.get_factory_config = AsyncMock(return_value={
            "llm_providers": {"dashscope": {"api_key": "default-key"}}
        })
        
        # Mock 保存版本
        mock_version = AsyncMock()
        mock_version.id = "v-factory-reset-001"
        mock_manager.save_new_version = AsyncMock(return_value=mock_version)
        
        response = client.post(
            "/api/v1/config/reset",
            json={"confirm": True, "reason": "测试恢复"},
            headers={"Authorization": f"Bearer {mock_user.token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["version_id"] == "v-factory-reset-001"
        assert "已恢复出厂设置" in data["message"]
        
        # 验证调用了 save_new_version
        mock_manager.save_new_version.assert_called_once()
        call_kwargs = mock_manager.save_new_version.call_args[1]
        assert call_kwargs["is_factory_reset"] is True
        assert "测试恢复" in call_kwargs["description"]

@pytest.mark.asyncio
async def test_reset_to_factory_without_confirm(client: TestClient, mock_user):
    """测试未二次确认时拒绝"""
    response = client.post(
        "/api/v1/config/reset",
        json={"confirm": False},
        headers={"Authorization": f"Bearer {mock_user.token}"}
    )
    
    assert response.status_code == 400
    assert "需要二次确认" in response.json()["detail"]

@pytest.mark.asyncio
async def test_reset_to_factory_audit_log(client: TestClient, mock_user):
    """测试审计日志记录"""
    with patch('src.controller.config_controller.config_manager') as mock_manager, \
         patch('src.controller.config_controller.ConfigAuditLogRepository') as mock_audit:
        
        mock_manager.get_factory_config = AsyncMock(return_value={})
        mock_version = AsyncMock()
        mock_version.id = "v-reset-002"
        mock_manager.save_new_version = AsyncMock(return_value=mock_version)
        mock_manager.current_version_id = "v-prev-001"
        
        mock_audit_repo = AsyncMock()
        mock_audit.return_value = mock_audit_repo
        
        response = client.post(
            "/api/v1/config/reset",
            json={"confirm": True},
            headers={"Authorization": f"Bearer {mock_user.token}"}
        )
        
        assert response.status_code == 200
        
        # 验证审计日志记录
        mock_audit_repo.create.assert_called_once()
        audit_data = mock_audit_repo.create.call_args[0][0]
        assert audit_data["action"].value == "RESET"
        assert audit_data["from_version"] == "v-prev-001"
        assert audit_data["to_version"] == "v-reset-002"
```

---

## 🐛 Bug 2: 保存 API 字段名不匹配

### 问题描述
前端 `configStore.ts` 第 84 行发送 `{config: draftChanges, description, created_by}`，但后端 `ConfigSaveRequest`（`config_controller.py:27`）期望 `{config_snapshot, description}`。

**后端已正确实现**，问题仅在前端发送了错误的字段名。

### 影响
保存配置失败，后端返回 422 验证错误。

### 修复方案

#### 方案：前端适配（唯一方案）

**文件:** `frontend/src/store/configStore.ts`

```typescript
saveConfig: async (description: string) => {
  const { draftChanges } = get();
  if (Object.keys(draftChanges).length === 0) return;

  set({ isSaving: true });
  try {
    // 适配后端字段名：config → config_snapshot
    await configApi.updateConfig({
      config_snapshot: draftChanges,  // 修正字段名
      description,
    });
    
    // 清空草稿，重新加载配置
    set({ draftChanges: {} });
    await get().loadConfig();
    await get().loadVersions();
  } finally {
    set({ isSaving: false });
  }
}
```

**注意**: 不需要后端兼容旧字段名，直接修正前端即可。

### 测试

**文件:** `backend/tests/api/test_config_save.py`

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_save_config_with_correct_field(client: TestClient, mock_user):
    """测试使用 config_snapshot 字段保存"""
    with patch('src.controller.config_controller.config_manager') as mock_manager:
        mock_version = AsyncMock()
        mock_version.id = "v-save-001"
        mock_version.created_at = "2026-04-15T10:00:00"
        mock_version.created_by = "testuser"
        mock_version.description = "测试保存"
        mock_version.parent_version_id = None
        mock_version.is_factory_reset = False
        
        mock_manager.save_new_version = AsyncMock(return_value=mock_version)
        
        response = client.post(
            "/api/v1/config/save",
            json={
                "config_snapshot": {"llm_providers": {"dashscope": {"api_key": "sk-test"}}},
                "description": "测试保存"
            },
            headers={"Authorization": f"Bearer {mock_user.token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "v-save-001"
        
        # 验证调用参数
        call_kwargs = mock_manager.save_new_version.call_args[1]
        assert "llm_providers" in call_kwargs["config_snapshot"]

@pytest.mark.asyncio
async def test_save_config_validation_error(client: TestClient, mock_user):
    """测试缺少 config_snapshot 时返回 422"""
    response = client.post(
        "/api/v1/config/save",
        json={"description": "缺少配置快照"},
        headers={"Authorization": f"Bearer {mock_user.token}"}
    )
    
    assert response.status_code == 422
```

---

## 🐛 Bug 3: 分类过滤逻辑缺陷

### 问题描述
`DynamicConfigForm.tsx` 的 `category` 过滤使用 `f.category === category` 精确匹配，但 Tree 支持 `mainCategory.subCategory` 层级，子分类过滤会失效。

### 影响
Tree 选择 `app.logging` 时，右侧不显示对应配置项。

### 修复方案

**文件:** `frontend/src/components/config/DynamicConfigForm.tsx`

```typescript
// 修复前（错误）
const filteredFields = fields.filter(f => f.category === category);

// 修复后（正确）
const filteredFields = fields.filter(f => {
  // 精确匹配或前缀匹配
  return f.category === category || f.category.startsWith(`${category}.`);
});
```

### 测试

**文件:** `frontend/src/components/config/__tests__/DynamicConfigForm.test.tsx`

```typescript
import { render, screen } from '@testing-library/react';
import { DynamicConfigForm } from '../DynamicConfigForm';

describe('DynamicConfigForm', () => {
  const mockFields = [
    { key: 'app.name', category: 'app', label: '应用名称', type: 'str', defaultValue: 'MyApp' },
    { key: 'app.logging.level', category: 'app.logging', label: '日志级别', type: 'str', defaultValue: 'INFO' },
    { key: 'app.logging.path', category: 'app.logging', label: '日志路径', type: 'str', defaultValue: '/var/log' },
    { key: 'rag.retrieval.strategy', category: 'rag.retrieval', label: '检索策略', type: 'select', defaultValue: 'hybrid' },
  ];

  test('should filter fields by parent category', () => {
    const { container } = render(
      <DynamicConfigForm 
        fields={mockFields} 
        selectedCategory="app"
        draftChanges={{}}
        onUpdateDraft={() => {}}
      />
    );

    // 选择 'app' 应显示 app 和 app.logging 的配置
    expect(screen.getByText('应用名称')).toBeInTheDocument();
    expect(screen.getByText('日志级别')).toBeInTheDocument();
    expect(screen.getByText('日志路径')).toBeInTheDocument();
    // 不应显示 rag 配置
    expect(screen.queryByText('检索策略')).not.toBeInTheDocument();
  });

  test('should filter fields by exact subcategory', () => {
    const { container } = render(
      <DynamicConfigForm 
        fields={mockFields} 
        selectedCategory="app.logging"
        draftChanges={{}}
        onUpdateDraft={() => {}}
      />
    );

    // 选择 'app.logging' 应仅显示 app.logging 的配置
    expect(screen.queryByText('应用名称')).not.toBeInTheDocument();
    expect(screen.getByText('日志级别')).toBeInTheDocument();
    expect(screen.getByText('日志路径')).toBeInTheDocument();
  });

  test('should show all fields when no category selected', () => {
    const { container } = render(
      <DynamicConfigForm 
        fields={mockFields} 
        selectedCategory={null}
        draftChanges={{}}
        onUpdateDraft={() => {}}
      />
    );

    expect(screen.getByText('应用名称')).toBeInTheDocument();
    expect(screen.getByText('日志级别')).toBeInTheDocument();
    expect(screen.getByText('检索策略')).toBeInTheDocument();
  });
});
```

---

## 🧹 技术债务清理

### 删除死代码

**操作:** 删除 `frontend/src/features/system-config/` 整个目录

包含文件：
- `ConfigManagementPage.tsx`
- `ConfigForm.tsx`
- `ConfigFieldRenderer.tsx`
- `schema.ts`
- `index.ts`

### 清理 ConfigStore 未使用状态

**文件:** `frontend/src/store/configStore.ts`

删除以下未使用状态：
- `isRunning`
- `lastResult`
- `comparisonBaseline`

---

## ✅ 验收清单

- [ ] **Bug 1:** `/api/v1/config/reset` 端点实现
  - [ ] 后端路由实现
  - [ ] ResetConfigRequest Schema
  - [ ] ConfigManager.get_factory_config() 方法
  - [ ] 前端二次确认对话框
  - [ ] 审计日志记录
  - [ ] 3 个测试用例通过

- [ ] **Bug 2:** 保存 API 字段名统一
  - [ ] 前端适配 config_snapshot 字段
  - [ ] 2 个测试用例通过

- [ ] **Bug 3:** 分类过滤逻辑修复
  - [ ] 支持前缀匹配（startsWith）
  - [ ] 1 个测试用例通过

- [ ] **技术债务:**
  - [ ] 删除 `features/system-config/` 目录
  - [ ] 清理 ConfigStore 未使用状态

---

## 📝 实施步骤

1. **Step 1:** 修复 Bug 1（恢复出厂设置）
   - 创建 ResetConfigRequest Schema
   - 实现 /reset 路由
   - 实现 ConfigManager.get_factory_config()
   - 前端添加二次确认
   - 编写测试并确认通过

2. **Step 2:** 修复 Bug 2（保存字段不匹配）
   - 修改 configStore.ts 适配 config_snapshot
   - 编写测试并确认通过

3. **Step 3:** 修复 Bug 3（分类过滤）
   - 修改 DynamicConfigForm.tsx 过滤逻辑
   - 编写测试并确认通过

4. **Step 4:** 清理技术债务
   - 删除死代码目录
   - 清理未使用状态
   - 验证页面功能正常

---

**返回总览：** [06-phase-4-00-overview.md](./06-phase-4-00-overview.md)
