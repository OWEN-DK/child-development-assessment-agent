# PDF/EPUB 二进制读取修复 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PDF/EPUB 二进制读取修复

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Modify: `backend/src/core/parsers.py`
- Modify: `backend/src/controller/rag_test_controller.py`
- Modify: `backend/src/service/rag_test_manager.py`
- Test: `backend/src/controller/rag_test_controller.py`

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

> **需求来源**: spec 文档 `01-phase-0-bug-fixes.md` 中 `2.0.1` 节
> **所属 Phase**: Phase 0
> **根因**: 用文本模式读取二进制文件，产生乱码；TXT 格式缺少解析器

---

## 需求定义

当前文档上传流程存在两个问题：

1. **PDF/EPUB 二进制处理**：虽然 `parsers.py` 中已有 `PDFParser`、`EPUBParser` 等专用解析器，但上传流程中可能存在用文本模式读取二进制文件的路径
2. **TXT 格式缺失**：前端 `UploadDocumentModal` 的 `accept` 属性包含 `.txt`，但 `get_parser()` 对 `.txt` 扩展名抛出 `ValueError`

**修复要求**：
1. PDF 文件必须通过 PyMuPDF（或 VLM 解析器）处理
2. EPUB 文件必须通过 ebooklib 处理
3. TXT 文件必须通过文本读取器处理
4. 上传流程使用二进制模式读取文件内容

---

## 验收标准

- [ ] 上传 PDF 文件能正确提取文本内容
- [ ] 上传 EPUB 文件能正确提取文本内容（含目录层级）
- [ ] 上传 TXT 文件能正确读取文本内容
- [ ] 不支持的格式返回明确的错误提示

---

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/parsers.py` | 修改 | 新增 TXT 解析器，完善 `get_parser()` |
| `backend/src/controller/rag_test_controller.py` | 检查 | 确认上传流程使用二进制模式 |
| `backend/src/service/rag_test_manager.py` | 检查 | 确认文档处理链路 |

---

## 实现方案

### 后端实现

**步骤 1：在 `parsers.py` 中新增 TXT 解析器**

```python
# backend/src/core/parsers.py

from llama_index.core import Document


class TXTParser:
    """纯文本文件解析器，支持自动编码检测"""
    
    def __init__(self):
        self.default_encoding = 'utf-8'
    
    def _detect_encoding(self, file_path: str) -> str:
        """自动检测文件编码
        
        参数:
            file_path: 文件路径
            
        返回:
            检测到的编码，检测失败时返回默认编码
        """
        try:
            import chardet
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # 读取前 10KB 用于检测
            result = chardet.detect(raw_data)
            return result.get('encoding') or self.default_encoding
        except ImportError:
            # chardet 未安装时使用默认编码
            return self.default_encoding
        except Exception:
            return self.default_encoding
    
    def parse(self, file_path: str) -> str:
        """读取 TXT 文件内容，自动检测编码
        
        参数:
            file_path: 文件路径
            
        返回:
            文本内容
        """
        encoding = self._detect_encoding(file_path)
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            return f.read()
    
    def parse_to_documents(self, file_path: str) -> list:
        """将 TXT 文件解析为 LlamaIndex Document 列表
        
        参数:
            file_path: 文件路径
            
        返回:
            Document 列表
        """
        text = self.parse(file_path)
        return [Document(text=text, metadata={'source': file_path})]
```

**步骤 2：修改 `get_parser()` 支持 TXT**

找到 `get_parser()` 函数（约在 `parsers.py` 末尾），修改为：

```python
def get_parser(file_extension: str):
    """根据文件扩展名返回对应的解析器
    
    参数:
        file_extension: 文件扩展名（含点号，如 '.pdf'）
        
    返回:
        对应的解析器实例
        
    异常:
        ValueError: 不支持的文件格式
    """
    ext = file_extension.lower()
    
    if ext == '.pdf':
        return PDFParserV2()  # 三级降级：VLM -> TEXT
    elif ext == '.epub':
        return EPUBParser()
    elif ext == '.txt':
        return TXTParser()
    else:
        raise ValueError(f'不支持的文件格式: {file_extension}。支持的格式: PDF, EPUB, TXT')
```

**步骤 3：确认上传流程使用二进制模式**

检查 `rag_test_controller.py` 中的上传端点，确保文件写入使用二进制模式：

```python
# backend/src/controller/rag_test_controller.py

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    title: str = Form(None),
    auto_generate: str = Form("true")
):
    """上传源文档"""
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
    
    # 使用二进制模式写入临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode='wb') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # 调用上传逻辑
        result = await rag_test_manager.upload_source_document(
            file_path=tmp_path,
            filename=file.filename,
            title=title,
            auto_generate=auto_generate == "true"
        )
        return result
    except Exception:
        raise  # 直接 re-raise，不重新抛出 e
    finally:
        # 确保临时文件被清理
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
```

**步骤 4：修复临时文件泄漏问题**

当前代码在异常时可能泄漏临时文件。使用 `try/finally` 确保清理：

```python
@router.post("/documents/upload")
async def upload_document(...):
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode='wb') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        result = await rag_test_manager.upload_source_document(...)
        return result
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass  # 忽略清理失败
```

---

## 测试方案

### 单元测试

```python
# backend/tests/test_parsers.py

import pytest
from src.core.parsers import TXTParser, get_parser

class TestTXTParser:
    def test_parse_simple_text(self, tmp_path):
        """测试简单 TXT 文件解析"""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("你好，世界！", encoding="utf-8")
        
        parser = TXTParser()
        result = parser.parse(str(txt_file))
        
        assert result == "你好，世界！"
    
    def test_parse_with_encoding_errors(self, tmp_path):
        """测试编码错误时的容错处理"""
        txt_file = tmp_path / "test.txt"
        # 写入包含无效 UTF-8 字节的内容
        txt_file.write_bytes(b"Hello \xff\xfe World")
        
        parser = TXTParser()
        result = parser.parse(str(txt_file))
        
        assert "Hello" in result  # errors='replace' 应替换无效字节
    
    def test_parse_to_documents(self, tmp_path):
        """测试转换为 Document 列表"""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("测试内容", encoding="utf-8")
        
        parser = TXTParser()
        docs = parser.parse_to_documents(str(txt_file))
        
        assert len(docs) == 1
        assert docs[0].text == "测试内容"
        assert docs[0].metadata['source'] == str(txt_file)

class TestGetParser:
    def test_txt_parser(self):
        """测试 TXT 解析器获取"""
        parser = get_parser('.txt')
        assert isinstance(parser, TXTParser)
    
    def test_pdf_parser(self):
        """测试 PDF 解析器获取"""
        parser = get_parser('.pdf')
        # PDFParserV2 实例
        assert parser is not None
    
    def test_epub_parser(self):
        """测试 EPUB 解析器获取"""
        parser = get_parser('.epub')
        assert parser is not None
    
    def test_unsupported_format(self):
        """测试不支持的格式"""
        with pytest.raises(ValueError, match="不支持的文件格式"):
            get_parser('.docx')
```

### 手动测试

1. 准备三个测试文件：`test.pdf`、`test.epub`、`test.txt`
2. 通过前端分别上传三个文件
3. 确认每个文件都能正确提取文本内容
4. 上传一个不支持的格式（如 `.docx`），确认返回明确的错误提示

---

## 注意事项

1. **编码处理**：TXT 文件可能使用不同编码（GBK、GB2312 等），当前使用 `utf-8` + `errors='replace'` 作为兜底。如需自动检测编码，可引入 `chardet` 库。
2. **大文件处理**：TXT 文件可能很大（如整本书），当前实现一次性读取全部内容。如需分块，可在 `parse_to_documents` 中使用 LlamaIndex 的 `SimpleNodeParser`。
3. **临时文件安全**：`tempfile.NamedTemporaryFile` 在 Windows 上无法在文件打开时被其他进程访问，当前方案使用 `delete=False` + 手动清理是正确做法。
4. **依赖检查**：确保 `pyproject.toml` 中已声明 `pymupdf`（PDF）、`ebooklib`（EPUB）依赖。

---

**返回索引：** [Phase 0 总览](../00-overview.md)
