#!/usr/bin/env python3
"""上传测试文档到知识库"""

import requests
import json

BASE_URL = "http://localhost:8000"

def upload_document(file_path: str):
    """上传文档"""
    print(f"正在上传：{file_path}")
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{BASE_URL}/rag/upload", files=files)
    
    print(f"状态码：{response.status_code}")
    result = response.json()
    print(f"响应：{json.dumps(result, indent=2, ensure_ascii=False)}")
    
    return result

if __name__ == "__main__":
    # 上传一本较小的 EPUB 文件进行测试
    test_file = "/Users/owen/project/ai/child-development-assessment-agent/book/学习如何学习.epub"
    result = upload_document(test_file)
    
    if result.get('status') == 'success' or 'task_id' in result:
        print("\n上传成功！等待处理完成...")
        print("提示：可以通过前端页面查看处理进度和分块详情")
    else:
        print("\n上传失败，请检查后端日志")
