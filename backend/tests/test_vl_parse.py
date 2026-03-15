import os
import fitz
import asyncio
from src.core.parsers import PDFVLParser
from src.config.settings import settings

TEST_PDF_PATH = "../../book/超越行为.pdf"
MAX_PAGES = 20  # 只解析前20页


async def test_vl_parsing():
    if not os.path.exists(TEST_PDF_PATH):
        print(f"测试PDF文件不存在: {TEST_PDF_PATH}")
        return

    if not settings.dashscope_api_key:
        print("DashScope API Key未配置，无法进行VL解析")
        return

    print(f"开始VL解析PDF前{MAX_PAGES}页: {TEST_PDF_PATH}")
    print("=" * 80)

    # 先获取PDF总页数
    doc = fitz.open(TEST_PDF_PATH)
    total_pages = len(doc)
    print(f"PDF总页数: {total_pages}，将解析前{min(MAX_PAGES, total_pages)}页")

    # 修改PDFVLParser的parse方法，只解析前N页
    original_parse = PDFVLParser.parse

    async def partial_parse(file_path, max_workers=None):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not settings.dashscope_api_key:
            raise ValueError("DashScope API Key is required for VL parsing.")

        doc = fitz.open(file_path)
        file_name = os.path.basename(file_path)
        total_pages = len(doc)
        # 只取前MAX_PAGES页
        parse_pages = min(MAX_PAGES, total_pages)
        documents = []

        if max_workers is None:
            max_workers = settings.rag_vl_max_workers

        logger.info(
            f"Starting VL parsing for {file_name} with {parse_pages} pages using {settings.model_vl_parsing}, {max_workers} threads"
        )

        # 准备页面参数列表，只取前N页
        page_args = [
            (doc[page_num], page_num, total_pages, file_name)
            for page_num in range(parse_pages)
        ]

        # 多线程并行处理
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(PDFVLParser._parse_single_page, args)
                for args in page_args
            ]

            for future in as_completed(futures):
                result = future.result()
                if result:
                    documents.append(result)

        doc.close()

        # 按页码排序
        documents.sort(key=lambda x: int(x.metadata["page_label"]))
        logger.info(f"VL parsing completed, {len(documents)} pages parsed successfully")

        return documents

    # 替换parse方法
    PDFVLParser.parse = partial_parse

    try:
        documents = await PDFVLParser.parse(TEST_PDF_PATH)
        print(f"\n✅ 解析完成，成功提取 {len(documents)} 页内容")

        # 打印前3页的内容示例
        for i, doc in enumerate(documents[:3]):
            print(f"\n第 {doc.metadata['page_label']} 页:")
            print(f"内容长度: {len(doc.text)} 字符")
            print(
                f"内容:\n{doc.text[:500]}..."
                if len(doc.text) > 500
                else f"内容:\n{doc.text}"
            )

        # 统计解析成功率
        success_rate = len(documents) / min(MAX_PAGES, total_pages) * 100
        print(f"\n解析成功率: {success_rate:.1f}%")

        if len(documents) > 0:
            avg_length = sum(len(d.text) for d in documents) / len(documents)
            print(f"平均每页文本长度: {avg_length:.0f} 字符")

    except Exception as e:
        print(f"\n❌ 解析失败: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    from src.utils.logger import logger

    asyncio.run(test_vl_parsing())
