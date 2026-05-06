import { useState, useCallback, useMemo } from 'react';
import { Modal, Transfer, message, Typography } from 'antd';
import type { TransferProps } from 'antd';
import { useTestCases } from '../../hooks/useTestCases';
import { useTestSet, useAddCasesToSet, useRemoveCasesFromSet } from '../../hooks/useTestSets';

const { Text } = Typography;

interface CaseTransferModalProps {
  open: boolean;
  setId: string;
  onClose: () => void;
}

interface TransferItem {
  key: string;
  query: string;
}

export function CaseTransferModal({ open, setId, onClose }: CaseTransferModalProps) {
  const [pendingTargetKeys, setPendingTargetKeys] = useState<string[] | null>(null);

  const { data: set } = useTestSet(setId);
  const { data } = useTestCases({ page_size: 100 });
  const addMutation = useAddCasesToSet();
  const removeMutation = useRemoveCasesFromSet();

  const allCases = data?.items || [];
  const savedTargetKeys = set?.case_ids || [];
  const targetKeys = pendingTargetKeys ?? savedTargetKeys;

  const dataSource: TransferItem[] = useMemo(
    () => allCases.map((c) => ({ key: c.id, query: c.query })),
    [allCases],
  );

  const handleChange: TransferProps['onChange'] = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    async (newTargetKeys: any, direction: any, moveKeys: any) => {
      const ids = (moveKeys as string[]).map(String);
      setPendingTargetKeys((newTargetKeys as string[]).map(String));
      try {
        if (direction === 'right') {
          await addMutation.mutateAsync({ setId, caseIds: ids });
          message.success(`已添加 ${ids.length} 个用例`);
        } else {
          await removeMutation.mutateAsync({ setId, caseIds: ids });
          message.success(`已移除 ${ids.length} 个用例`);
        }
      } catch {
        setPendingTargetKeys(null);
      }
    },
    [setId, addMutation, removeMutation],
  );

  const filterOption = (inputValue: string, item: TransferItem) =>
    item.query.toLowerCase().includes(inputValue.toLowerCase());

  return (
    <Modal
      title={`管理测试用例 — ${set?.name || ''}`}
      open={open}
      onCancel={onClose}
      footer={null}
      width={860}
      destroyOnClose
    >
      <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
        当前测试集已包含 {set?.case_count ?? 0} 个用例，共 {allCases.length} 个可选
      </Text>
      <Transfer
        dataSource={dataSource}
        targetKeys={targetKeys}
        onChange={handleChange}
        showSearch
        filterOption={filterOption}
        listStyle={{ width: 380, height: 480 }}
        titles={['可添加', '已添加']}
        render={(item) => (
          <Text ellipsis style={{ flex: 1, fontSize: 12 }} title={item.query}>
            {item.query}
          </Text>
        )}
      />
    </Modal>
  );
}
