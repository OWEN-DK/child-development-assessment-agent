#!/usr/bin/env python3
"""
清理卡住的任务并重置文档状态
"""
import os
import sys
import json
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.src.service.document_manager import document_manager
from backend.src.service.document_ingestion_service import import_task_manager

def cleanup_stuck_tasks(max_age_hours=24):
    """清理卡住的任务"""
    print("=" * 80)
    print("清理卡住的任务")
    print("=" * 80)
    
    now = datetime.now()
    cleaned_count = 0
    
    for filename in os.listdir(import_task_manager.task_dir):
        if not filename.endswith(".json"):
            continue
        
        file_path = os.path.join(import_task_manager.task_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                task_state = json.load(f)
            
            # 检查任务状态
            status = task_state.get("status", "unknown")
            created_at_str = task_state.get("created_at", "")
            file_name = task_state.get("file_name", "unknown")
            file_hash = task_state.get("file_hash", "")
            
            # 解析创建时间
            try:
                created_at = datetime.fromisoformat(created_at_str)
                age = now - created_at
            except Exception:
                age = timedelta(days=365)  # 如果解析失败，假设很老
            
            # 判断是否需要清理
            should_clean = False
            reason = ""
            
            if status == "running" and age > timedelta(hours=max_age_hours):
                should_clean = True
                reason = f"运行时间过长 ({age})"
            elif status == "failed" and age > timedelta(days=7):
                should_clean = True
                reason = f"失败任务超过 7 天 ({age})"
            
            if should_clean:
                print(f"\n清理任务：{filename}")
                print(f"  - 文件名：{file_name}")
                print(f"  - 文件哈希：{file_hash}")
                print(f"  - 状态：{status}")
                print(f"  - 创建时间：{created_at}")
                print(f"  - 原因：{reason}")
                
                # 删除任务状态文件
                os.remove(file_path)
                print(f"  - 已删除任务状态文件")
                
                # 如果文档存在，也删除文档记录
                if file_hash and document_manager.exists(file_hash):
                    doc = document_manager.get_document(file_hash)
                    print(f"  - 删除文档记录：{doc.file_name if doc else file_hash}")
                    document_manager.delete_document(file_hash)
                
                cleaned_count += 1
                
        except Exception as e:
            print(f"处理任务状态文件 {filename} 时出错：{e}")
    
    print(f"\n{'=' * 80}")
    print(f"清理完成，共清理 {cleaned_count} 个卡住的任务")
    print(f"{'=' * 80}")

def list_current_tasks():
    """列出当前所有任务"""
    print("\n当前任务列表:")
    print("-" * 80)
    
    for filename in os.listdir(import_task_manager.task_dir):
        if not filename.endswith(".json"):
            continue
        
        file_path = os.path.join(import_task_manager.task_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                task_state = json.load(f)
            
            print(f"\n任务：{filename}")
            print(f"  - 文件名：{task_state.get('file_name', 'unknown')}")
            print(f"  - 文件哈希：{task_state.get('file_hash', '')}")
            print(f"  - 状态：{task_state.get('status', 'unknown')}")
            print(f"  - 阶段：{task_state.get('current_stage', 'unknown')}")
            print(f"  - 进度：{task_state.get('progress', 0)}%")
            print(f"  - 创建时间：{task_state.get('created_at', 'unknown')}")
        except Exception as e:
            print(f"读取任务 {filename} 失败：{e}")

if __name__ == "__main__":
    print("当前任务状态:")
    list_current_tasks()
    
    print("\n\n")
    cleanup_stuck_tasks(max_age_hours=1)  # 清理超过 1 小时的任务
    
    print("\n清理后的任务状态:")
    list_current_tasks()
