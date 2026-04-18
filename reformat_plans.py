import os
import glob
import re

base_dir = "/Users/owen/project/ai/child-development-assessment-agent/docs/superpowers/plans/rag-evaluation-page-refactoring/phases"

md_files = glob.glob(f"{base_dir}/**/*.md", recursive=True)

count = 0
for file_path in md_files:
    if file_path.endswith("00-overview.md"):
        continue

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "> **For agentic workers:** REQUIRED" in content:
        continue

    # Extract title
    title_match = re.search(r"^#\s+(.+)$", content, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else os.path.basename(file_path).replace(".md", "")
    
    new_title = title if title.endswith("Implementation Plan") else f"{title} Implementation Plan"

    # Extract files
    files_to_create = []
    files_to_modify = []
    test_files = []
    
    file_table_match = re.search(r"\| 文件路径.*?\| 操作.*?\| 说明.*?\n\|[-|]+\n((?:\|.*?\n)+)", content)
    if file_table_match:
        rows = file_table_match.group(1).strip().split("\n")
        for row in rows:
            parts = [p.strip().strip("`") for p in row.split("|") if p.strip()]
            if len(parts) >= 2:
                file_path_str = parts[0]
                op = parts[1]
                if "新增" in op or "创建" in op:
                    files_to_create.append(file_path_str)
                elif "测试" in op:
                    test_files.append(file_path_str)
                else:
                    files_to_modify.append(file_path_str)

    # Search for tests in code blocks
    test_file_match = re.search(r"//\s*([a-zA-Z0-9_/-]+\.test\.[tj]sx?)", content)
    if test_file_match:
        test_files.append(test_file_match.group(1))
    test_file_match_py = re.search(r"#\s*([a-zA-Z0-9_/-]*test_[a-zA-Z0-9_/-]+\.py)", content)
    if test_file_match_py:
        test_files.append(test_file_match_py.group(1))

    # Fallback tests
    if not test_files:
        if any("frontend" in f for f in files_to_modify + files_to_create):
            test_files.append("frontend/src/__tests__/placeholder.test.ts")
        if any("backend" in f for f in files_to_modify + files_to_create):
            test_files.append("backend/tests/test_placeholder.py")
        if not test_files:
            test_files.append("tests/test_placeholder.py")

    # Remove duplicates
    test_files = list(dict.fromkeys(test_files))
    files_to_create = list(dict.fromkeys(files_to_create))
    files_to_modify = list(dict.fromkeys(files_to_modify))

    content_without_title = re.sub(r"^#\s+.*?\n", "", content, count=1).strip()
    
    new_content = f"""# {new_title}

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** {title}

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
"""
    for f in files_to_create:
        new_content += f"- Create: `{f}`\n"
    for f in files_to_modify:
        new_content += f"- Modify: `{f}`\n"
    for f in test_files:
        new_content += f"- Test: `{f}`\n"
        
    new_content += f"""
- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

{content_without_title}
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    count += 1

print(f"Successfully processed {count} files.")