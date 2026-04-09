#!/usr/bin/env python3
"""测试分块 API 是否正常工作"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_get_documents():
    """测试获取文档列表"""
    print("=" * 60)
    print("测试 1: 获取文档列表")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/rag/documents")
    print(f"状态码：{response.status_code}")
    print(f"响应：{json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()
    
    return response.json().get('documents', [])

def test_get_chunks(file_hash: str):
    """测试获取分块"""
    print("=" * 60)
    print(f"测试 2: 获取文档 {file_hash} 的分块")
    print("=" * 60)
    
    response = requests.get(
        f"{BASE_URL}/rag/documents/{file_hash}/chunks",
        params={"page": 1, "page_size": 20}
    )
    print(f"状态码：{response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"总数：{data.get('total', 0)}")
        print(f"当前页：{data.get('page', 0)}")
        print(f"每页数量：{data.get('page_size', 0)}")
        print(f"分块数量：{len(data.get('chunks', []))}")
        
        if data.get('chunks'):
            print("\n第一个分块:")
            chunk = data['chunks'][0]
            print(f"  ID: {chunk.get('id', '')[:50]}...")
            print(f"  内容：{chunk.get('content', '')[:200]}...")
            print(f"  元数据：{json.dumps(chunk.get('metadata', {}), indent=2, ensure_ascii=False)[:500]}...")
    else:
        print(f"错误：{response.text}")
    print()

if __name__ == "__main__":
    documents = test_get_documents()
    
    if documents:
        print(f"\n找到 {len(documents)} 个文档")
        for doc in documents[:1]:  # 只测试第一个文档
            test_get_chunks(doc['file_hash'])
    else:
        print("\n没有找到文档，请先上传文档！")
        print("提示：可以通过前端页面上传 PDF 或 EPUB 文档")
