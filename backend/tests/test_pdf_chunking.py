import os
import asyncio
from src.core.parsers import PDFParser
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.dashscope import DashScopeEmbedding
from src.config.settings import settings
from src.utils.logger import logger

# 测试PDF文件路径，用book目录下的任意PDF，如果没有就用临时上传的
TEST_PDF_PATH = "../../book/超越行为.pdf"
if not os.path.exists(TEST_PDF_PATH):
    TEST_PDF_PATH = "./temp_uploads/test.pdf"

async def test_pdf_chunking():
    if not os.path.exists(TEST_PDF_PATH):
        print(f"测试PDF文件不存在: {TEST_PDF_PATH}")
        print("请先上传一个PDF文件到book目录或temp_uploads目录")
        return
    
    print(f"开始测试PDF chunking和embedding: {TEST_PDF_PATH}")
    print("=" * 80)
    
    # 1. 测试PDF解析
    print("\n1. 测试PDF解析:")
    parser = PDFParser()
    documents = parser.parse(TEST_PDF_PATH)
    print(f"解析得到 {len(documents)} 个页面文档")
    
    if not documents:
        print("PDF解析失败，没有得到任何内容")
        return
    
    # 打印前2个页面的内容示例
    for i, doc in enumerate(documents[:2]):
        print(f"\n页面 {i+1} (页码: {doc.metadata.get('page_label')}):")
        print(f"内容长度: {len(doc.text)} 字符")
        print(f"内容前200字: {doc.text[:200]}...")
    
    # 2. 测试chunk分割
    print("\n" + "=" * 80)
    print("\n2. 测试Chunk分割:")
    splitter = SentenceSplitter(chunk_size=1536, chunk_overlap=20)
    all_chunks = []
    for doc in documents:
        chunks = splitter.get_nodes_from_documents([doc])
        all_chunks.extend(chunks)
    
    print(f"分割得到 {len(all_chunks)} 个chunk")
    
    # 打印前3个chunk的信息
    for i, chunk in enumerate(all_chunks[:3]):
        print(f"\nChunk {i+1}:")
        print(f"长度: {len(chunk.text)} 字符")
        print(f"元数据: {chunk.metadata}")
        print(f"内容前150字: {chunk.text[:150]}...")
    
    # 统计chunk长度分布
    avg_length = sum(len(c.text) for c in all_chunks) / len(all_chunks)
    min_length = min(len(c.text) for c in all_chunks)
    max_length = max(len(c.text) for c in all_chunks)
    print(f"\nChunk长度统计: 平均={avg_length:.0f}, 最小={min_length}, 最大={max_length}")
    
    # 3. 测试embedding生成
    print("\n" + "=" * 80)
    print("\n3. 测试Embedding生成:")
    
    if not settings.dashscope_api_key:
        print("DashScope API Key未配置，跳过embedding测试")
        return
    
    embed_model = DashScopeEmbedding(
        model_name="text-embedding-v2", 
        api_key=settings.dashscope_api_key
    )
    
    # 生成前3个chunk的embedding
    test_texts = [chunk.text for chunk in all_chunks[:3]]
    try:
        embeddings = embed_model.get_text_embedding_batch(test_texts)
        print(f"成功生成 {len(embeddings)} 个embedding")
        for i, emb in enumerate(embeddings):
            print(f"Embedding {i+1} 维度: {len(emb)}")
            print(f"前5个值: {emb[:5]}...")
        
        # 测试相似度计算
        if len(embeddings) >= 2:
            import numpy as np
            sim = np.dot(embeddings[0], embeddings[1]) / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]))
            print(f"\nChunk 1 和 Chunk 2 的余弦相似度: {sim:.4f}")
            
    except Exception as e:
        print(f"Embedding生成失败: {str(e)}")
        return
    
    print("\n" + "=" * 80)
    print("\n✅ PDF chunking和embedding测试完成!")
    print(f"总结:")
    print(f"- 解析页数: {len(documents)}")
    print(f"- 生成chunk数: {len(all_chunks)}")
    print(f"- 平均chunk长度: {avg_length:.0f} 字符")
    print(f"- Embedding维度: {len(embeddings[0]) if embeddings else 'N/A'}")

if __name__ == "__main__":
    asyncio.run(test_pdf_chunking())
