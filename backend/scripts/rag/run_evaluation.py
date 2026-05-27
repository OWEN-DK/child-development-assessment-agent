#!/usr/bin/env python3
"""Import test set and create test run for RAG evaluation"""
import json, requests, time, sys

BASE = 'http://localhost:8000/api/v1/rag/eval'

# Step 1: Check how many cases already exist
resp = requests.get(f'{BASE}/test-cases?page=1&page_size=1')
existing_total = resp.json()['data']['total']
print(f'Existing test cases: {existing_total}')

# Step 2: Import remaining
with open('src/data/test_sets/rag_evaluation_test_set_v1.json', 'r') as f:
    data = json.load(f)

if existing_total >= len(data):
    print(f'All {len(data)} cases already imported, skipping import')
else:
    cases = []
    for item in data:
        cases.append({
            'query': item['query'],
            'description': item.get('description', ''),
            'expected_knowledge_ids': item.get('expected_knowledge_ids', []),
            'expected_keywords': item.get('expected_keywords', []),
        })
    
    all_ids = []
    batch_size = 20
    for i in range(0, len(cases), batch_size):
        batch = cases[i:i+batch_size]
        t0 = time.time()
        try:
            resp = requests.post(f'{BASE}/test-cases/import', json={'cases': batch}, timeout=120)
            result = resp.json()
            elapsed = time.time() - t0
            if result['code'] == 0:
                ids = [item['id'] for item in result['data']['items']]
                all_ids.extend(ids)
                print(f'Batch {i//batch_size + 1}/{(len(cases)+batch_size-1)//batch_size}: {len(ids)} cases, {elapsed:.1f}s')
            else:
                print(f'Batch {i//batch_size + 1} FAILED: {result["message"]}')
        except Exception as e:
            print(f'Batch {i//batch_size + 1} ERROR: {e}')
    
    print(f'Newly imported: {len(all_ids)}')

# Step 3: Fetch all case IDs
all_case_ids = []
page = 1
while True:
    resp = requests.get(f'{BASE}/test-cases?page={page}&page_size=100')
    result = resp.json()
    items = result['data']['items']
    if not items:
        break
    all_case_ids.extend([item['id'] for item in items])
    if len(items) < 100:
        break
    page += 1

print(f'Total case IDs collected: {len(all_case_ids)}')

# Step 4: Create test set
resp = requests.post(f'{BASE}/test-sets', json={
    'name': 'RAG 评测集 v1',
    'description': f'{len(all_case_ids)} 条来自 rag_evaluation_test_set_v1.json 的评测用例',
    'case_ids': all_case_ids,
})
ts_result = resp.json()
print(f'Test set created: {json.dumps(ts_result, ensure_ascii=False)[:300]}')

if ts_result['code'] != 0:
    # Try listing existing test sets
    resp = requests.get(f'{BASE}/test-sets')
    sets = resp.json().get('data', [])
    print(f'Existing test sets: {len(sets)}')
    if sets:
        ts_result = {'data': sets[0]}
        print(f'Using existing test set: {sets[0].get("name")}')

ts_id = ts_result['data'].get('id') if ts_result.get('data') else None
if not ts_id:
    print('ERROR: No test set ID found')
    sys.exit(1)

# Step 5: Create test run
resp = requests.post(f'{BASE}/runs', json={
    'test_set_id': ts_id,
    'name': 'RAG 基线评测运行',
    'description': '对当前 RAG 配置的基线评测',
    'config_snapshot_enabled': True,
})
run_result = resp.json()
print(f'Test run: {json.dumps(run_result, ensure_ascii=False)[:300]}')

run_id = run_result['data'].get('id') if run_result.get('data') else None

# Step 6: Execute the run
if run_id:
    resp = requests.post(f'{BASE}/runs/{run_id}/execute')
    exec_result = resp.json()
    print(f'Execute: {json.dumps(exec_result, ensure_ascii=False)[:300]}')
    task_id = exec_result.get('data', {}).get('task_id')
    print(f'\nRun ID: {run_id}')
    print(f'Task ID: {task_id}')
    
    # Save state
    with open('/tmp/rag_eval_state.json', 'w') as f:
        json.dump({
            'case_ids': all_case_ids,
            'total_cases': len(all_case_ids),
            'test_set_id': ts_id,
            'run_id': run_id,
            'task_id': task_id,
        }, f, ensure_ascii=False)
