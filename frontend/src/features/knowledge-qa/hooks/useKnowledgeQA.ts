/**
 * 知识问答 hook — 薄包装层
 *
 * SSE 管理和状态都已在 knowledgeQAStore 中，
 * hook 仅负责组件挂载/卸载时的 SSE 生命周期。
 */

import { useEffect, useCallback } from 'react';
import { useKnowledgeQAStore } from '../stores/knowledgeQAStore';

export function useKnowledgeQA() {
  const store = useKnowledgeQAStore();

  // 组件挂载/卸载 → 触发 store 的 SSE 生命周期
  useEffect(() => {
    store.onMount();
    return store.onUnmount;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const ask = useCallback(
    (question: string, bookIds?: string[]) => store.ask(question, bookIds),
    [], // eslint-disable-line react-hooks/exhaustive-deps
  );

  const cancel = useCallback(() => store.cancel(), []);

  return {
    ask,
    cancel,
    status: store.status,
    progress: store.progress,
    result: store.result,
    error: store.error,
  };
}
