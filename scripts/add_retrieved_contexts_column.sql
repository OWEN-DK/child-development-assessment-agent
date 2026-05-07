-- 为 test_run_results 表添加 retrieved_contexts 列
-- 用于存储检索上下文文本，修复 L2 指标（faithfulness/groundedness）低分问题

ALTER TABLE `test_run_results`
ADD COLUMN `retrieved_contexts` JSON COMMENT '检索上下文文本列表'
AFTER `retrieved_doc_ids`;
