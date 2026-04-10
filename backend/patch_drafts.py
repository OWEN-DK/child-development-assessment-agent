import json
import os

drafts_path = 'storage/test_case_drafts/drafts.json'
if os.path.exists(drafts_path):
    with open(drafts_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for idx, (draft_id, draft) in enumerate(data.get('drafts', {}).items()):
        if not draft.get('description'):
            draft['description'] = f"这是一条自动生成的测试用例草稿描述_{idx+1}"
        if not draft.get('expected_knowledge_ids'):
            draft['expected_knowledge_ids'] = [f"knowledge_{idx}_A", f"knowledge_{idx}_B"]
        if not draft.get('expected_keywords'):
            draft['expected_keywords'] = [f"关键词{idx}A", f"关键词{idx}B"]
        if not draft.get('answer_points'):
            draft['answer_points'] = ["这是答题要点1", "这是答题要点2"]
        if not draft.get('professional_terms'):
            draft['professional_terms'] = ["术语A", "术语B"]
        if not draft.get('age_requirement'):
            draft['age_requirement'] = "0-6岁"
            
    with open(drafts_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Drafts patched.")