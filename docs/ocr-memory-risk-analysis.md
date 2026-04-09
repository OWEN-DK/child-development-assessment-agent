# OCR 内存风险分析报告

> 分析日期：2026-04-03  
> 分析范围：`backend/src/core/parsers.py` 及相关文件  
> 风险等级：🔴 高 | 🟡 中 | 🟢 低

---

## 一、核心 OCR 代码架构

### 1.1 主要组件

| 组件 | 文件 | 行号 | 说明 |
|------|------|------|------|
| `PDFVLParser` | [parsers.py](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/parsers.py#L156-L280) | 156-280 | 主 OCR/VLM 解析器 |
| `PDFParserV2` | [parsers.py](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/parsers.py#L438-L581) | 438-581 | 三级降级解析器 |
| 扫描版检测 | [document_ingestion_service.py](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/service/document_ingestion_service.py#L617-L688) | 617-688 | 自动切换 VL 解析 |

### 1.2 图像处理流程

```
PDF 打开 → 页面渲染为 Pixmap → 保存为临时 PNG → 调用 Qwen-VL → 清理临时文件 → 关闭 PDF
```

### 1.3 现有内存管理措施

| 措施 | 位置 | 状态 |
|------|------|------|
| 临时文件清理 | [parsers.py:226-228](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/parsers.py#L226-L228) | ✅ 使用 `finally` 块 |
| PDF 文档关闭 | [parsers.py:274](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/parsers.py#L274) | ✅ 解析后关闭 |
| 并发控制 | [settings.py:274](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/config/settings.py#L274) | ✅ 默认 2 线程 |
| LRU 缓存 | [cache_service.py](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/service/cache_service.py) | ✅ 有最大大小限制 |

---

## 二、内存风险详细分析

### 🔴 风险 1：多线程共享 PDF 对象（高风险）

**位置**: [parsers.py:257-260](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/parsers.py#L257-L260)

**问题描述**:
```python
# 当前代码
page_args = [
    (doc[page_num], page_num, total_pages, file_name)
    for page_num in range(total_pages)
]

with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [
        executor.submit(PDFVLParser._parse_single_page, args)
        for args in page_args
    ]
```

**风险详情**:
- `doc[page_num]` 返回的 `Page` 对象被传递到多个线程
- PyMuPDF 的 `Page` 对象**不是线程安全的**
- 所有线程共享同一个 `doc` 对象的引用
- 多线程并发访问可能导致：
  - 内存损坏（Memory Corruption）
  - 段错误（Segmentation Fault）
  - 数据竞争（Data Race）
  - 不可预测的崩溃

**影响范围**: 
- 任何使用 `PDFVLParser.parse()` 的场景
- 默认配置下 2 个并发线程即可触发
- 大文档（多页 PDF）风险更高

**修复方案**:

```python
@staticmethod
def _parse_single_page(args: Tuple[int, int, str, str]) -> Optional[Document]:
    """
    解析单个PDF页面，每个线程独立打开PDF文档
    """
    page_num, total_pages, file_name, file_path = args
    
    # 每个线程独立打开 PDF 文档
    doc = fitz.open(file_path)
    try:
        page = doc[page_num]
        
        # Render page to image
        mat = fitz.Matrix(1.0, 1.0)
        pix = page.get_pixmap(matrix=mat)
        
        try:
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                pix.save(tmp_img.name)
                tmp_img_path = tmp_img.name
            
            try:
                # Call Qwen-VL
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"image": f"file://{tmp_img_path}"},
                            {
                                "text": "请提取这张图片中的所有文字内容，保持原有的段落结构。只输出提取的文字，不要输出任何其他解释或描述。"
                            },
                        ],
                    }
                ]
                
                response = dashscope.MultiModalConversation.call(
                    model=settings.model_vl_parsing,
                    messages=messages,
                    api_key=settings.dashscope_api_key,
                )
                
                text = ""
                if response.status_code == HTTPStatus.OK:
                    if response.output and response.output.choices:
                        content_list = response.output.choices[0].message.content
                        if isinstance(content_list, list):
                            text = "".join(
                                [item["text"] for item in content_list if "text" in item]
                            )
                        elif isinstance(content_list, str):
                            text = content_list
                else:
                    logger.error(
                        f"VL Parsing failed for page {page_num}: {response.message}"
                    )
                
                if not text.strip():
                    logger.warning(f"Page {page_num} yielded empty text via VL.")
                    return None
                
                metadata = {
                    "file_name": file_name,
                    "page_label": str(page_num + 1),
                    "total_pages": total_pages,
                    "parsing_method": "qwen-vl",
                }
                
                logger.info(f"Parsed page {page_num + 1}/{total_pages} via VL.")
                return Document(text=text, metadata=metadata)
                
            except Exception as e:
                logger.error(f"Error parsing page {page_num} with VL: {e}")
                return None
            finally:
                if os.path.exists(tmp_img_path):
                    os.remove(tmp_img_path)
        finally:
            pix = None  # 显式释放 Pixmap
    finally:
        doc.close()  # 每个线程独立关闭

@staticmethod
def parse(file_path: str, max_workers: int = None) -> List[Document]:
    """
    Parse PDF file using Qwen-VL for OCR/understanding (for scanned PDFs).
    使用多线程并行解析，每个线程独立打开PDF文档，确保线程安全。
    Returns a list of Documents, one per page.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if not settings.dashscope_api_key:
        raise ValueError("DashScope API Key is required for VL parsing.")
    
    doc = fitz.open(file_path)
    file_name = os.path.basename(file_path)
    total_pages = len(doc)
    doc.close()  # 立即关闭，不在多线程中使用
    
    if max_workers is None:
        max_workers = settings.rag_vl_max_workers
    
    logger.info(
        f"Starting VL parsing for {file_name} with {total_pages} pages using {settings.model_vl_parsing}, {max_workers} threads"
    )
    
    # 准备页面参数列表（传递文件路径而非 Page 对象）
    page_args = [
        (page_num, total_pages, file_name, file_path)
        for page_num in range(total_pages)
    ]
    
    documents = []
    
    # 多线程并行处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(PDFVLParser._parse_single_page, args)
            for args in page_args
        ]
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                documents.append(result)
    
    # 按页码排序，保证输出顺序正确
    documents.sort(key=lambda x: int(x.metadata["page_label"]))
    logger.info(f"VL parsing completed, {len(documents)} pages parsed successfully")
    
    return documents
```

---

### 🟡 风险 2：Pixmap 对象未显式释放（中等风险）

**位置**: [parsers.py:166](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/parsers.py#L166)

**问题描述**:
```python
pix = page.get_pixmap(matrix=mat)
pix.save(tmp_img.name)
# pix 没有显式释放，依赖 Python GC
```

**风险详情**:
- PyMuPDF 的 `Pixmap` 对象持有**原生内存**（C/C++ 层面分配）
- Python 的垃圾回收可能不会立即释放原生内存
- 高分辨率 PDF 页面（如 300 DPI）的单个 Pixmap 可能占用 **数十 MB** 内存
- 默认 2 个并发线程，理论上最多 2 个 Pixmap 同时存在
- 如果 GC 延迟，可能累积更多 Pixmap 对象

**内存估算**:
```
A4 页面 @ 150 DPI: 约 1240 x 1754 像素
内存占用: 1240 * 1754 * 3 bytes ≈ 6.5 MB

A4 页面 @ 300 DPI: 约 2480 x 3508 像素
内存占用: 2480 * 3508 * 3 bytes ≈ 26 MB
```

**修复方案**:

```python
pix = page.get_pixmap(matrix=mat)
try:
    pix.save(tmp_img.name)
finally:
    pix = None  # 显式释放引用，触发原生内存释放
```

**增强方案**（添加页面大小检查）:

```python
MAX_PAGE_SIZE_MB = 50  # 单页最大 50MB

pix = page.get_pixmap(matrix=mat)
try:
    # 检查页面大小
    estimated_size_mb = (pix.width * pix.height * 3) / (1024 * 1024)
    if estimated_size_mb > MAX_PAGE_SIZE_MB:
        logger.warning(
            f"Page {page_num} too large ({estimated_size_mb:.1f}MB), "
            f"reducing resolution"
        )
        pix = None
        # 降低分辨率重新渲染
        mat = fitz.Matrix(0.5, 0.5)
        pix = page.get_pixmap(matrix=mat)
    
    pix.save(tmp_img.name)
finally:
    pix = None
```

---

### 🟡 风险 3：文件句柄泄漏（中等风险）

**位置**: [pageindex_wrapper.py:251-253](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/pageindex_wrapper.py#L251-L253)

**问题描述**:
```python
data.add_field('file',
              open(file_path, 'rb'),
              filename=os.path.basename(file_path))
```

**风险详情**:
- `open(file_path, 'rb')` 创建的文件对象没有显式关闭
- 依赖 aiohttp 内部实现来关闭文件句柄
- 如果请求失败或抛出异常，文件句柄可能泄漏
- 长期运行可能导致文件描述符耗尽

**修复方案**:

```python
# 方案 1：使用上下文管理器
with open(file_path, 'rb') as f:
    data.add_field('file', f, filename=os.path.basename(file_path))
    # 发送请求...
    response = await session.post(url, data=data)

# 方案 2：使用 aiofiles 异步文件操作
import aiofiles

async with aiofiles.open(file_path, 'rb') as f:
    file_content = await f.read()
    data.add_field('file', file_content, filename=os.path.basename(file_path))
```

---

### 🟢 风险 4：临时文件在异常情况下可能残留（低风险）

**位置**: [parsers.py:169-171](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/core/parsers.py#L169-L171)

**问题描述**:
```python
with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
    pix.save(tmp_img.name)
    tmp_img_path = tmp_img.name
```

**风险详情**:
- 虽然 `finally` 块中有清理逻辑，但如果 `pix.save()` 本身抛出异常
- `tmp_img_path` 可能未被赋值，导致 `finally` 块中的 `os.remove()` 因变量未定义而跳过
- 实际影响较低，因为 `tmp_img_path` 在 `with` 块内已赋值

**修复方案**:

```python
tmp_img_path = None
try:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
        pix.save(tmp_img.name)
        tmp_img_path = tmp_img.name
    
    # ... 处理逻辑 ...
    
finally:
    if tmp_img_path and os.path.exists(tmp_img_path):
        os.remove(tmp_img_path)
```

---

### 🟢 风险 5：测试文件中的资源泄漏（低风险）

**位置**: [test_vl_parse.py:38](file:///Users/owen/project/ai/child-development-assessment-agent/backend/tests/test_vl_parse.py#L38)

**问题描述**:
```python
doc = fitz.open(file_path)
# ... 使用 doc
doc.close()
```

**风险详情**:
- 测试代码中如果中间抛出异常，`doc.close()` 不会被执行
- 应使用 `with` 语句或 `try/finally`

**修复方案**:

```python
with fitz.open(file_path) as doc:
    # ... 使用 doc
    # 自动关闭
```

---

### 🟢 风险 6：缓存锁对象累积（低风险）

**位置**: [cache_service.py:70, 259-260](file:///Users/owen/project/ai/child-development-assessment-agent/backend/src/service/cache_service.py#L70)

**问题描述**:
```python
self.locks = {}
# ...
lock = self.locks.get(lock_key, asyncio.Lock())
self.locks[lock_key] = lock
```

**风险详情**:
- `locks` 字典会持续增长，即使锁已经不再使用也不会被清理
- 虽然第 285-286 行有清理逻辑，但只在特定条件下执行
- 长期运行可能累积大量无用锁对象

**修复方案**:

```python
# 定期清理未使用的锁
def _cleanup_locks(self):
    """清理不再活跃的锁对象"""
    active_keys = set(self.memory_cache.keys())
    inactive_keys = set(self.locks.keys()) - active_keys
    for key in inactive_keys:
        del self.locks[key]
```

---

## 三、修复优先级建议

| 优先级 | 风险 | 修复难度 | 建议时间 |
|--------|------|----------|----------|
| **P0** | 多线程共享 PDF 对象 | 低 | 立即修复 |
| **P1** | Pixmap 对象未显式释放 | 低 | 尽快修复 |
| **P1** | 文件句柄泄漏 | 低 | 尽快修复 |
| **P2** | 临时文件异常残留 | 低 | 可选修复 |
| **P2** | 测试代码资源泄漏 | 低 | 可选修复 |
| **P2** | 缓存锁对象累积 | 中 | 可选修复 |

---

## 四、完整修复代码

### 4.1 `PDFVLParser` 完整修复版本

```python
class PDFVLParser:
    @staticmethod
    def _parse_single_page(args: Tuple[int, int, str, str]) -> Optional[Document]:
        """
        解析单个PDF页面，每个线程独立打开PDF文档，确保线程安全
        """
        page_num, total_pages, file_name, file_path = args
        
        # 每个线程独立打开 PDF 文档
        doc = fitz.open(file_path)
        try:
            page = doc[page_num]
            
            # Render page to image
            mat = fitz.Matrix(1.0, 1.0)
            pix = page.get_pixmap(matrix=mat)
            
            tmp_img_path = None
            try:
                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                    pix.save(tmp_img.name)
                    tmp_img_path = tmp_img.name
                
                # 显式释放 Pixmap
                pix = None
                
                # Call Qwen-VL
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"image": f"file://{tmp_img_path}"},
                            {
                                "text": "请提取这张图片中的所有文字内容，保持原有的段落结构。只输出提取的文字，不要输出任何其他解释或描述。"
                            },
                        ],
                    }
                ]
                
                response = dashscope.MultiModalConversation.call(
                    model=settings.model_vl_parsing,
                    messages=messages,
                    api_key=settings.dashscope_api_key,
                )
                
                text = ""
                if response.status_code == HTTPStatus.OK:
                    if response.output and response.output.choices:
                        content_list = response.output.choices[0].message.content
                        if isinstance(content_list, list):
                            text = "".join(
                                [item["text"] for item in content_list if "text" in item]
                            )
                        elif isinstance(content_list, str):
                            text = content_list
                else:
                    logger.error(
                        f"VL Parsing failed for page {page_num}: {response.message}"
                    )
                
                if not text.strip():
                    logger.warning(f"Page {page_num} yielded empty text via VL.")
                    return None
                
                metadata = {
                    "file_name": file_name,
                    "page_label": str(page_num + 1),
                    "total_pages": total_pages,
                    "parsing_method": "qwen-vl",
                }
                
                logger.info(f"Parsed page {page_num + 1}/{total_pages} via VL.")
                return Document(text=text, metadata=metadata)
                
            except Exception as e:
                logger.error(f"Error parsing page {page_num} with VL: {e}")
                return None
            finally:
                if tmp_img_path and os.path.exists(tmp_img_path):
                    os.remove(tmp_img_path)
        finally:
            doc.close()

    @staticmethod
    def parse(file_path: str, max_workers: int = None) -> List[Document]:
        """
        Parse PDF file using Qwen-VL for OCR/understanding (for scanned PDFs).
        使用多线程并行解析，每个线程独立打开PDF文档，确保线程安全。
        Returns a list of Documents, one per page.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not settings.dashscope_api_key:
            raise ValueError("DashScope API Key is required for VL parsing.")
        
        # 仅获取总页数，立即关闭文档
        doc = fitz.open(file_path)
        file_name = os.path.basename(file_path)
        total_pages = len(doc)
        doc.close()
        
        if max_workers is None:
            max_workers = settings.rag_vl_max_workers
        
        logger.info(
            f"Starting VL parsing for {file_name} with {total_pages} pages using {settings.model_vl_parsing}, {max_workers} threads"
        )
        
        # 准备页面参数列表（传递文件路径而非 Page 对象）
        page_args = [
            (page_num, total_pages, file_name, file_path)
            for page_num in range(total_pages)
        ]
        
        documents = []
        
        # 多线程并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(PDFVLParser._parse_single_page, args)
                for args in page_args
            ]
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    documents.append(result)
        
        # 按页码排序，保证输出顺序正确
        documents.sort(key=lambda x: int(x.metadata["page_label"]))
        logger.info(f"VL parsing completed, {len(documents)} pages parsed successfully")
        
        return documents
```

---

## 五、监控建议

### 5.1 添加内存监控

```python
import psutil
import os

def log_memory_usage(stage: str):
    """记录当前内存使用情况"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    logger.info(
        f"[Memory] {stage}: "
        f"RSS={memory_info.rss / 1024 / 1024:.1f}MB, "
        f"VMS={memory_info.vms / 1024 / 1024:.1f}MB"
    )

# 在关键位置调用
log_memory_usage("Before VL parsing")
# ... 解析逻辑 ...
log_memory_usage("After VL parsing")
```

### 5.2 添加并发限制

```python
# 根据可用内存动态调整并发数
def get_optimal_workers(total_pages: int) -> int:
    """根据页面数和可用内存计算最优线程数"""
    process = psutil.Process(os.getpid())
    available_memory_mb = psutil.virtual_memory().available / 1024 / 1024
    
    # 估算每页最大内存占用（300 DPI）
    max_memory_per_page_mb = 30
    
    # 计算安全并发数
    safe_workers = int(available_memory_mb / (max_memory_per_page_mb * 2))
    
    # 限制在合理范围内
    return max(1, min(safe_workers, settings.rag_vl_max_workers, total_pages))
```

---

## 六、总结

### 6.1 关键发现

1. **最严重问题**: 多线程共享 PyMuPDF 的 `Page` 对象，可能导致内存损坏和崩溃
2. **次要问题**: Pixmap 对象未显式释放，可能导致内存累积
3. **潜在问题**: 文件句柄泄漏，长期运行可能耗尽文件描述符

### 6.2 修复效果预期

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 线程安全性 | ❌ 不安全 | ✅ 安全 |
| 内存泄漏风险 | 🟡 中等 | 🟢 低 |
| 文件句柄泄漏 | 🟡 中等 | 🟢 低 |
| 崩溃风险 | 🔴 高 | 🟢 低 |

### 6.3 后续建议

1. **立即实施**: 修复多线程共享问题（P0）
2. **短期优化**: 显式释放 Pixmap 和文件句柄（P1）
3. **长期规划**: 
   - 添加内存监控和告警
   - 实现动态并发控制
   - 考虑使用异步 IO 替代多线程
   - 定期运行内存泄漏检测工具（如 `tracemalloc`）
