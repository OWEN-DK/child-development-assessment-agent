# A-6: 前端分数展示适配

> **所属 Phase**: Phase A (P0)
> **任务类型**: 单一任务 — 前端响应类型更新与分数展示适配
> **对应需求**: 4.1 验收标准（前端能分别展示两个分数）

## 🎯 目标

前端适配后端分数语义变更：
1. API 响应类型新增 `age_fit_score` 字段
2. 搜索结果组件分别展示 `relevance_score` 和 `age_fit_score`
3. 保持向后兼容（`age_fit_score` 缺失时默认 0.0）

## 📋 实施步骤

- [ ] **Step 1: 更新 API 响应类型**
  - [ ] **1.1 阅读当前类型定义**：
    - [ ] 文件位置：`frontend/src/api/knowledge/types.ts`
    - [ ] 当前 `SearchResultItem` 接口（第 1-13 行）：
      ```typescript
      export interface SearchResultItem {
        id: string;
        content: string;
        score: number;
        source_book: string;
        chapter_title?: string;
        page_label?: string;
        target_age_min: number;
        target_age_max: number;
        brain_regions: string[];
        topics: string[];
        file_hash: string;
      }
      ```
    - [ ] **注意**：前端使用 `SearchResultItem` 而非 `KnowledgeItem`，对应后端 `_process_search_results` 返回的字典
  
  - [ ] **1.2 修改 `SearchResultItem` 接口**：
    - [ ] 新增 `age_fit_score` 字段（可选，保持向后兼容）：
      ```typescript
      export interface SearchResultItem {
        id: string;
        content: string;
        score: number;  // 检索相关性分数（对应后端 display_score）
        age_fit_score?: number;  // 新增：年龄适配度分数（0-1，可选）
        source_book: string;
        chapter_title?: string;
        page_label?: string;
        target_age_min: number;
        target_age_max: number;
        brain_regions: string[];
        topics: string[];
        file_hash: string;
      }
      ```
    - [ ] **说明**：
      - `age_fit_score` 使用可选标记 `?`，确保旧版 API 响应（无此字段）不崩溃
      - 默认值处理在组件中完成（见 Step 3）
  
  - [ ] **1.3 检查是否有其他类型定义需要更新**：
    - [ ] 搜索 `frontend/src` 中是否有其他引用 `SearchResultItem` 的地方：
      ```bash
      cd frontend && grep -rn "SearchResultItem" src/ --include="*.ts" --include="*.tsx"
      ```
    - [ ] 确认以下文件使用 `SearchResultItem`：
      - `src/components/knowledge/SearchResultList.tsx`
      - `src/components/knowledge/ResultDetailModal.tsx`
      - `src/features/knowledge/hooks/useKnowledgeSearch.ts`
      - `src/features/knowledge/pages/KnowledgeSearchPage.tsx`
      - `src/api/knowledge/index.ts`
    - [ ] 这些文件无需修改类型导入，仅需在展示逻辑中处理新字段

- [ ] **Step 2: 更新搜索结果组件**
  - [ ] **2.1 修改 `SearchResultList.tsx`**（搜索结果列表）：
    - [ ] 文件位置：`frontend/src/components/knowledge/SearchResultList.tsx`
    - [ ] **定位当前分数展示**（第 71 行）：
      ```tsx
      <Tag color="blue">相关度: {(item.score * 100).toFixed(1)}%</Tag>
      ```
    - [ ] **修改为双分数展示**：
      ```tsx
      <Space size="small" wrap>
        <Tag color="blue">
          检索相关度: {(item.score * 100).toFixed(1)}%
        </Tag>
        {item.age_fit_score !== undefined && item.age_fit_score !== null && (
          <Tag color={getAgeFitScoreColor(item.age_fit_score)}>
            年龄适配度: {(item.age_fit_score * 100).toFixed(1)}%
          </Tag>
        )}
        <Tag color="green">来源: {item.source_book}</Tag>
        {item.page_label && (
          <Tag color="orange">
            {/^\d+$/.test(item.page_label) ? 
              '第 ' + item.page_label + ' 页' : 
              item.page_label.includes('/') ? 
                '章节: ' + (item.chapter_title || item.page_label.split('/').pop()) : 
                item.page_label
            }
          </Tag>
        )}
      </Space>
      ```
    - [ ] **添加颜色辅助函数**（在组件外部或文件顶部添加）：
      ```tsx
      /**
       * 根据年龄适配度分数返回 Tag 颜色
       * @param score 年龄适配度分数 (0-1)
       * @returns 颜色字符串
       */
      const getAgeFitScoreColor = (score: number): string => {
        if (score >= 0.8) return 'green';    // 高适配
        if (score >= 0.6) return 'blue';     // 中适配
        if (score >= 0.4) return 'orange';   // 低适配
        return 'red';                        // 不适配
      };
      ```
  
  - [ ] **2.2 修改 `ResultDetailModal.tsx`**（详情弹窗）：
    - [ ] 文件位置：`frontend/src/components/knowledge/ResultDetailModal.tsx`
    - [ ] **定位当前相关度展示**（第 48-50 行）：
      ```tsx
      <Descriptions.Item label="相关度">
        {(item.score * 100).toFixed(2)}%
      </Descriptions.Item>
      ```
    - [ ] **修改为双分数展示**：
      ```tsx
      <Descriptions.Item label="检索相关度">
        {(item.score * 100).toFixed(2)}%
      </Descriptions.Item>
      {item.age_fit_score !== undefined && item.age_fit_score !== null && (
        <Descriptions.Item label="年龄适配度">
          <span style={{ color: getAgeFitScoreColor(item.age_fit_score) }}>
            {(item.age_fit_score * 100).toFixed(2)}%
          </span>
        </Descriptions.Item>
      )}
      ```
    - [ ] **添加颜色辅助函数**（在组件外部或文件顶部添加）：
      ```tsx
      /**
       * 根据年龄适配度分数返回颜色
       * @param score 年龄适配度分数 (0-1)
       * @returns 颜色字符串
       */
      const getAgeFitScoreColor = (score: number): string => {
        if (score >= 0.8) return '#52c41a';  // 绿色：高适配
        if (score >= 0.6) return '#1890ff';  // 蓝色：中适配
        if (score >= 0.4) return '#fa8c16';  // 橙色：低适配
        return '#f5222d';                    // 红色：不适配
      };
      ```
  
  - [ ] **2.3 添加 Tooltip 说明**（可选，提升用户体验）：
    - [ ] 在 `SearchResultList.tsx` 中为分数 Tag 添加 Tooltip：
      ```tsx
      import { Tooltip } from 'antd';
      
      // 在分数 Tag 外层包裹 Tooltip
      <Tooltip title="检索相关度：内容与查询关键词的相关程度，来自 Cross-Encoder 重排序">
        <Tag color="blue">
          检索相关度: {(item.score * 100).toFixed(1)}%
        </Tag>
      </Tooltip>
      {item.age_fit_score !== undefined && item.age_fit_score !== null && (
        <Tooltip title="年龄适配度：内容适合用户当前年龄的程度，基于年龄范围、内容特征和领域匹配度计算">
          <Tag color={getAgeFitScoreColor(item.age_fit_score)}>
            年龄适配度: {(item.age_fit_score * 100).toFixed(1)}%
          </Tag>
        </Tooltip>
      )}
      ```
    - [ ] 在 `ResultDetailModal.tsx` 中为 Descriptions.Item 添加 Tooltip：
      ```tsx
      import { Tooltip } from 'antd';
      import { QuestionCircleOutlined } from '@ant-design/icons';
      
      // 在 label 旁添加帮助图标
      <Descriptions.Item label={
        <span>
          检索相关度
          <Tooltip title="内容与查询关键词的相关程度，来自 Cross-Encoder 重排序">
            <QuestionCircleOutlined style={{ marginLeft: 4, color: '#999' }} />
          </Tooltip>
        </span>
      }>
        {(item.score * 100).toFixed(2)}%
      </Descriptions.Item>
      {item.age_fit_score !== undefined && item.age_fit_score !== null && (
        <Descriptions.Item label={
          <span>
            年龄适配度
            <Tooltip title="内容适合用户当前年龄的程度，基于年龄范围、内容特征和领域匹配度计算">
              <QuestionCircleOutlined style={{ marginLeft: 4, color: '#999' }} />
            </Tooltip>
          </span>
        }>
          <span style={{ color: getAgeFitScoreColor(item.age_fit_score) }}>
            {(item.age_fit_score * 100).toFixed(2)}%
          </span>
        </Descriptions.Item>
      )}
      ```

- [ ] **Step 3: 向后兼容处理**
  - [ ] **3.1 处理 `age_fit_score` 缺失的情况**：
    - [ ] 在 `SearchResultList.tsx` 中：
      ```tsx
      // 使用可选链和空值合并运算符
      const ageFitScore = item.age_fit_score ?? 0.0;
      
      // 或者在展示时检查
      {item.age_fit_score !== undefined && item.age_fit_score !== null ? (
        <Tag color={getAgeFitScoreColor(item.age_fit_score)}>
          年龄适配度: {(item.age_fit_score * 100).toFixed(1)}%
        </Tag>
      ) : (
        <Tag color="default">年龄适配度: 未计算</Tag>
      )}
      ```
    - [ ] 在 `ResultDetailModal.tsx` 中：
      ```tsx
      {item.age_fit_score !== undefined && item.age_fit_score !== null ? (
        <Descriptions.Item label="年龄适配度">
          <span style={{ color: getAgeFitScoreColor(item.age_fit_score) }}>
            {(item.age_fit_score * 100).toFixed(2)}%
          </span>
        </Descriptions.Item>
      ) : (
        <Descriptions.Item label="年龄适配度">
          未计算
        </Descriptions.Item>
      )}
      ```
  
  - [ ] **3.2 确保排序逻辑不受影响**：
    - [ ] 当前前端排序由后端完成（后端按 `relevance_score` 排序后返回）
    - [ ] 前端无需修改排序逻辑
    - [ ] 如果前端有本地排序（如分页后重新排序），确保使用 `score` 字段：
      ```typescript
      // 示例：前端本地排序（如有）
      const sortedResults = [...results].sort((a, b) => b.score - a.score);
      ```
  
  - [ ] **3.3 验证旧版 API 响应兼容性**：
    - [ ] 模拟旧版 API 响应（无 `age_fit_score` 字段）：
      ```typescript
      const oldResponse: SearchResultItem = {
        id: "test_001",
        content: "测试内容",
        score: 0.85,
        source_book: "测试书",
        target_age_min: 3,
        target_age_max: 4,
        brain_regions: [],
        topics: [],
        file_hash: "abc123"
        // 无 age_fit_score 字段
      };
      ```
    - [ ] 确认组件渲染不崩溃（TypeScript 编译通过，运行时不报错）

- [ ] **Step 4: 集成验证**
  - [ ] **4.1 前端编译验证**：
    ```bash
    cd frontend
    npm run build
    ```
    - [ ] 确认无 TypeScript 编译错误
    - [ ] 确认无 ESLint 错误
  
  - [ ] **4.2 前端启动验证**：
    ```bash
    cd frontend
    npm run dev
    ```
    - [ ] 访问 `/knowledge` 路由
    - [ ] 执行搜索（如"感统训练"）
    - [ ] 确认搜索结果列表正常展示
    - [ ] 确认每个结果展示两个分数（检索相关度、年龄适配度）
    - [ ] 点击"查看详情"，确认弹窗正常展示两个分数
    - [ ] 检查浏览器控制台无 JavaScript 错误
  
  - [ ] **4.3 验证分数颜色逻辑**：
    ```typescript
    // 在浏览器控制台运行
    const testScores = [0.9, 0.75, 0.5, 0.3, 0.1];
    const getColor = (score) => {
      if (score >= 0.8) return 'green';
      if (score >= 0.6) return 'blue';
      if (score >= 0.4) return 'orange';
      return 'red';
    };
    testScores.forEach(score => {
      console.log(`score=${score}, color=${getColor(score)}`);
    });
    // 期望输出：
    // score=0.9, color=green
    // score=0.75, color=blue
    // score=0.5, color=orange
    // score=0.3, color=red
    // score=0.1, color=red
    ```
  
  - [ ] **4.4 验证向后兼容**：
    - [ ] 使用 Mock 数据模拟旧版 API 响应：
      ```typescript
      // 在测试文件中
      const mockOldResponse = {
        total: 1,
        results: [{
          id: "test_001",
          content: "测试内容",
          score: 0.85,
          source_book: "测试书",
          target_age_min: 3,
          target_age_max: 4,
          brain_regions: [],
          topics: [],
          file_hash: "abc123"
          // 无 age_fit_score
        }]
      };
      ```
    - [ ] 确认组件渲染正常，年龄适配度显示"未计算"或不显示
  
  - [ ] **4.5 验证 Tooltip 交互**：
    - [ ] 鼠标悬停在分数 Tag 上
    - [ ] 确认 Tooltip 正确展示说明文字
    - [ ] 确认说明文字准确描述分数含义
  
  - [ ] **4.6 响应式布局验证**：
    - [ ] 在不同屏幕尺寸下测试（桌面、平板、手机）
    - [ ] 确认分数 Tag 正确换行（使用 `wrap` 属性）
    - [ ] 确认 Tooltip 不被截断

## ✅ 验收标准

- `KnowledgeItem` 接口新增 `age_fit_score` 字段
- 搜索结果页同时展示 `relevance_score` 和 `age_fit_score`
- 分数含义通过 Tooltip 明确说明
- 旧版 API 响应兼容（不崩溃）

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/api/knowledge/types.ts` | 修改 | `SearchResultItem` 新增 `age_fit_score?: number` 字段 |
| `frontend/src/components/knowledge/SearchResultList.tsx` | 修改 | 分数展示适配，新增年龄适配度 Tag 和 Tooltip |
| `frontend/src/components/knowledge/ResultDetailModal.tsx` | 修改 | 详情弹窗分数展示适配，新增年龄适配度 Descriptions.Item |

---

**返回索引：** [01-phase-a-00-overview.md](./01-phase-a-00-overview.md)
