#!/usr/bin/env python3
"""文档导入质量评估脚本"""
import sys
import os
import json
import time
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.service.document_manager import document_manager
from src.service.index_manager_service import index_manager
from src.config.settings import settings
from src.utils.logger import logger

def extract_age_ranges_from_metadata(metadata: dict) -> list:
    """从元数据中提取年龄范围"""
    age_ranges = []
    age_patterns = settings.rule_metadata_age_patterns
    
    for field in ['age_range', 'applicable_age', 'description', 'content']:
        text = str(metadata.get(field, ''))
        for pattern in age_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    ages = [int(m) for m in match if m.isdigit()]
                    if len(ages) >= 2:
                        age_ranges.append((min(ages), max(ages)))
                    elif len(ages) == 1:
                        age_ranges.append((ages[0], ages[0]))
                elif match.isdigit():
                    age = int(match)
                    age_ranges.append((age, age))
    
    return age_ranges

def evaluate_chunk_metadata_completeness(chunks: list) -> float:
    """评估元数据完整度"""
    if not chunks:
        return 0.0
    
    required_fields = ['file_hash', 'page_label', 'age_range']
    complete_count = 0
    
    for chunk in chunks:
        metadata = chunk.get('metadata', {})
        fields_present = sum(1 for field in required_fields if metadata.get(field))
        if fields_present == len(required_fields):
            complete_count += 1
    
    return complete_count / len(chunks)

def evaluate_age_range_coverage(chunks: list) -> float:
    """评估年龄范围覆盖率"""
    if not chunks:
        return 0.0
    
    chunks_with_age = 0
    for chunk in chunks:
        metadata = chunk.get('metadata', {})
        age_ranges = extract_age_ranges_from_metadata(metadata)
        if age_ranges:
            chunks_with_age += 1
    
    return chunks_with_age / len(chunks)

def evaluate_ingestion_quality():
    """评估文档导入质量"""
    docs = document_manager.list_documents()
    
    if not docs:
        print("警告：知识库中没有文档")
        return
    
    print(f"知识库中共有 {len(docs)} 个文档")
    
    # 获取所有分块
    all_chunks = []
    for doc in docs:
        try:
            chunks_info = index_manager.get_document_chunks(doc.file_hash)
            chunks = chunks_info.get('chunks', [])
            all_chunks.extend(chunks)
        except Exception as e:
            logger.error(f"获取文档 {doc.file_name} 的分块失败: {e}")
    
    total_chunks = len(all_chunks)
    print(f"总共有 {total_chunks} 个分块")
    
    if total_chunks == 0:
        print("警告：没有分块数据")
        return
    
    # 计算平均块长度
    total_length = sum(len(chunk.get('content', '')) for chunk in all_chunks)
    avg_chunk_length = total_length / total_chunks
    
    # 评估元数据完整度
    metadata_completeness = evaluate_chunk_metadata_completeness(all_chunks)
    
    # 评估年龄范围覆盖率
    age_range_coverage = evaluate_age_range_coverage(all_chunks)
    
    # 评估语义分块质量（基于块长度分布）
    chunk_lengths = [len(chunk.get('content', '')) for chunk in all_chunks]
    reasonable_chunks = sum(1 for length in chunk_lengths 
                          if settings.rag_chunk_size * 0.5 <= length <= settings.rag_chunk_size * 1.5)
    semantic_chunking_accuracy = reasonable_chunks / total_chunks if total_chunks > 0 else 0.0
    
    print(f"\n=== 文档导入质量评估报告 ===")
    print(f"总文档数: {len(docs)}")
    print(f"总分块数: {total_chunks}")
    print(f"平均块长度: {avg_chunk_length:.0f}")
    print(f"元数据完整度: {metadata_completeness:.2%}")
    print(f"年龄范围覆盖率: {age_range_coverage:.2%}")
    print(f"语义分块准确率: {semantic_chunking_accuracy:.2%}")
    
    report = {
        "timestamp": time.time(),
        "total_documents": len(docs),
        "metrics": {
            "total_chunks": total_chunks,
            "avg_chunk_length": round(avg_chunk_length, 2),
            "metadata_completeness": round(metadata_completeness, 4),
            "age_range_coverage": round(age_range_coverage, 4),
            "semantic_chunking_accuracy": round(semantic_chunking_accuracy, 4),
        },
        "config": {
            "chunk_size": settings.rag_chunk_size,
            "chunk_overlap": settings.rag_chunk_overlap,
            "semantic_splitter_threshold": settings.semantic_splitter_breakpoint_threshold,
        }
    }
    
    os.makedirs("backend/reports", exist_ok=True)
    report_path = "backend/reports/ingestion_quality_report_v1.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存到: {report_path}")
    
    # 达标检查
    print(f"\n=== 达标检查 ===")
    checks = [
        ("元数据完整度 >= 95%", metadata_completeness >= 0.95),
        ("年龄范围覆盖率 >= 90%", age_range_coverage >= 0.90),
        ("语义分块准确率 >= 95%", semantic_chunking_accuracy >= 0.95),
    ]
    for name, passed in checks:
        status = "✅ 通过" if passed else "❌ 未达标"
        print(f"  {name}: {status}")

if __name__ == "__main__":
    evaluate_ingestion_quality()
