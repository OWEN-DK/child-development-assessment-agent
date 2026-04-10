from pathlib import Path
import json
from datetime import datetime

def migrate_test_cases():
    """迁移现有测试用例，为新增字段设置默认值"""
    store_path = Path("./storage/test_cases.json")
    
    if not store_path.exists():
        print("No test cases to migrate")
        return
    
    with open(store_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    migrated_count = 0
    
    for case_id, case in data.get("test_cases", {}).items():
        needs_save = False
        
        # 为新增字段设置默认值
        if "domain" not in case or case["domain"] == "":
            case["domain"] = "未知"
            needs_save = True
        
        if "answer_points" not in case:
            case["answer_points"] = []
            needs_save = True
        
        if "professional_terms" not in case:
            case["professional_terms"] = []
            needs_save = True
        
        if "age_requirement" not in case or case["age_requirement"] == "":
            case["age_requirement"] = ""
            needs_save = True
        
        if "relevance_scores" not in case:
            case["relevance_scores"] = {}
            needs_save = True
        
        if "source_document_id" not in case:
            case["source_document_id"] = ""
            needs_save = True
        
        if "test_set_id" not in case:
            case["test_set_id"] = ""
            needs_save = True
        
        if "version" not in case:
            case["version"] = 1
            needs_save = True
        
        if needs_save:
            migrated_count += 1
    
    if migrated_count > 0:
        # 备份原文件
        backup_path = store_path.with_suffix(f".backup.{datetime.now().strftime('%Y%m%d%H%M%S')}")
        store_path.rename(backup_path)
        
        # 写入新数据
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Migrated {migrated_count} test cases")
        print(f"Backup saved to {backup_path}")
    else:
        print("No test cases need migration")

if __name__ == "__main__":
    migrate_test_cases()
