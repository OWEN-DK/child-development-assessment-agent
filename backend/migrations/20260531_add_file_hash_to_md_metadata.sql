-- 修复 'MDMetadata' object has no attribute 'file_hash' 错误
-- 需要执行以下 SQL 将 file_hash 列添加到 md_metadata 表
ALTER TABLE md_metadata ADD COLUMN file_hash VARCHAR(64) NULL;
