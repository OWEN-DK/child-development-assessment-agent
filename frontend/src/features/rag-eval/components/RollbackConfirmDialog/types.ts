/**
 * 回滚确认对话框组件类型定义
 */

export interface ConfigVersionInfo {
  id: string;
  version_label: string;
  version_number: number;
  created_at: string | null;
}

export interface RollbackConfirmDialogProps {
  visible: boolean;
  targetVersion: ConfigVersionInfo | null;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
  loading?: boolean;
}
