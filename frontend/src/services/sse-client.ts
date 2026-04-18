/**
 * SSE客户端实现
 * 
 * 负责连接后端SSE端点、解析事件、分发给各页面组件，并处理断线重连。
 * 支持10种SSE事件类型，心跳超时检测，指数退避重连。
 */

import type { SseEvent, SseEventHandler, RecoveryState } from '@/types/sse-events';

export interface SseClientOptions {
  baseUrl?: string;
  heartbeatTimeout?: number;  // 心跳超时阈值（毫秒），默认45000
  reconnectBaseDelay?: number; // 重连基础延迟（毫秒），默认1000
  reconnectMaxDelay?: number;  // 重连最大延迟（毫秒），默认30000
  maxReconnectAttempts?: number; // 最大重连次数，默认0（无限）
}

export class SseClient {
  private eventSource: EventSource | null = null;
  private handlers: Map<string, Set<SseEventHandler>> = new Map();
  private heartbeatTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private isManualClose = false;
  private currentRunId: string | null = null;

  constructor(private options: SseClientOptions = {}) {}

  /**
   * 连接SSE端点
   */
  connect(runId: string): void {
    this.isManualClose = false;
    this.reconnectAttempts = 0;
    this.currentRunId = runId;
    this.createEventSource(runId);
  }

  /**
   * 连接导出SSE通道
   */
  connectExports(userId: string): void {
    this.isManualClose = false;
    this.reconnectAttempts = 0;
    this.createExportEventSource(userId);
  }

  /**
   * 注册事件处理器
   * @returns 取消订阅函数
   */
  on(eventType: string, handler: SseEventHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler);

    // 返回取消订阅函数
    return () => {
      this.handlers.get(eventType)?.delete(handler);
    };
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    this.isManualClose = true;
    this.cleanup();
  }

  /**
   * 创建EventSource（测试运行通道）
   */
  private createEventSource(runId: string): void {
    const apiBaseUrl = this.options.baseUrl || import.meta.env.VITE_API_BASE_URL || '';
    // 如果 apiBaseUrl 以 http:// 开头，需要将其转换为正确的代理前缀或直接请求后端
    // 如果是开发环境，通常让浏览器直接请求带代理的路径
    const url = `${apiBaseUrl.startsWith('http') && apiBaseUrl.includes('localhost:8000') ? '' : apiBaseUrl}/api/v1/rag/test/runs/${runId}/sse`;
    
    this.cleanup(); // 清理旧连接
    this.eventSource = new EventSource(url);

    this.eventSource.onmessage = (event: MessageEvent) => {
      try {
        const data: SseEvent = JSON.parse(event.data);
        this.resetHeartbeat();
        this.dispatch(data);
      } catch (e) {
        console.error('SSE事件解析失败:', e, event.data);
      }
    };

    this.eventSource.onerror = () => {
      this.cleanup();
      if (!this.isManualClose && this.currentRunId) {
        this.scheduleReconnect(this.currentRunId);
      }
    };

    this.resetHeartbeat();
  }

  /**
   * 创建EventSource（导出通道）
   */
  private createExportEventSource(userId: string): void {
    const apiBaseUrl = this.options.baseUrl || import.meta.env.VITE_API_BASE_URL || '';
    const url = `${apiBaseUrl.startsWith('http') && apiBaseUrl.includes('localhost:8000') ? '' : apiBaseUrl}/api/v1/rag/test/sse/exports?user_id=${userId}`;
    
    this.cleanup();
    this.eventSource = new EventSource(url);

    this.eventSource.onmessage = (event: MessageEvent) => {
      try {
        const data: SseEvent = JSON.parse(event.data);
        this.dispatch(data);
      } catch (e) {
        console.error('SSE事件解析失败:', e, event.data);
      }
    };

    this.eventSource.onerror = () => {
      this.cleanup();
      if (!this.isManualClose) {
        // 导出通道不需要重连，导出是瞬时事件
        console.warn('导出SSE连接断开');
      }
    };
  }

  /**
   * 重置心跳计时器
   */
  private resetHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer);
    }
    this.heartbeatTimer = setTimeout(
      () => this.handleHeartbeatTimeout(),
      this.options.heartbeatTimeout || 45000
    );
  }

  /**
   * 处理心跳超时
   */
  private handleHeartbeatTimeout(): void {
    console.warn('SSE心跳超时，判定断线');
    this.eventSource?.close();
    this.eventSource = null;
    // 触发重连（由onerror回调处理）
  }

  /**
   * 调度重连
   */
  private scheduleReconnect(runId: string): void {
    const maxAttempts = this.options.maxReconnectAttempts || 0;
    if (maxAttempts > 0 && this.reconnectAttempts >= maxAttempts) {
      console.error('SSE重连次数已达上限，停止重连');
      this.dispatch({ type: 'reconnect_failed' } as SseEvent);
      return;
    }

    // 先尝试恢复进度
    this.recoverProgress(runId).then(state => {
      if (state) {
        this.handleReconnect(runId, state);
        // 如果运行已完成或失败，不需要重连SSE
        if (state.status === 'completed' || state.status === 'failed' || state.status === 'cancelled') {
          return;
        }
      }
      // 仍在运行，建立新连接
      const delay = this.calculateReconnectDelay();
      console.log(`SSE将在${delay}ms后重连（第${this.reconnectAttempts + 1}次）`);

      setTimeout(() => {
        this.reconnectAttempts++;
        this.createEventSource(runId);
      }, delay);
    });
  }

  /**
   * 计算重连延迟（指数退避）
   */
  private calculateReconnectDelay(): number {
    const base = this.options.reconnectBaseDelay || 1000;
    const max = this.options.reconnectMaxDelay || 30000;
    // 指数退避：1s, 2s, 4s, 8s, 16s, 30s, 30s...
    return Math.min(base * Math.pow(2, this.reconnectAttempts), max);
  }

  /**
   * 恢复进度（查询后端API）
   */
  private async recoverProgress(runId: string): Promise<RecoveryState | null> {
    try {
      const apiBaseUrl = this.options.baseUrl || import.meta.env.VITE_API_BASE_URL || '';
      const url = `${apiBaseUrl.startsWith('http') && apiBaseUrl.includes('localhost:8000') ? '' : apiBaseUrl}/rag/test/runs/${runId}`;
      const response = await fetch(url);
      if (!response.ok) return null;
      const data = await response.json();
      return {
        run_id: runId,
        status: data.status,
        current: data.passed_test_cases || 0,
        total: data.total_test_cases || 0,
        metrics: {
          precision: data.overall_precision || 0,
          recall: data.overall_recall || 0,
          f1: data.overall_f1 || 0,
          mrr: data.overall_mrr || 0,
          ndcg: data.overall_ndcg || 0,
        },
        error: data.error_message,
      };
    } catch {
      return null;
    }
  }

  /**
   * 处理重连后的状态恢复
   */
  private handleReconnect(runId: string, state: RecoveryState): void {
    // 分发状态恢复事件，让前端组件处理
    this.dispatch({
      type: 'progress',
      run_id: runId,
      current_case: state.current,
      total_cases: state.total,
      timestamp: new Date().toISOString(),
    } as SseEvent);

    // 如果运行已完成，分发test_completed事件
    if (state.status === 'completed') {
      this.dispatch({
        type: 'test_completed',
        run_id: runId,
        total_cases: state.total,
        passed_cases: state.current,
        overall_metrics: state.metrics || { precision: 0, recall: 0, f1: 0, mrr: 0, ndcg: 0 },
        timestamp: new Date().toISOString(),
      } as SseEvent);
    }

    // 如果运行失败，分发run_failed事件
    if (state.status === 'failed') {
      this.dispatch({
        type: 'run_failed',
        run_id: runId,
        error_code: state.error_code || 'UNKNOWN',
        error_message: state.error || '未知错误',
        timestamp: new Date().toISOString(),
      } as SseEvent);
    }
  }

  /**
   * 分发事件到所有注册的处理器
   */
  private dispatch(event: SseEvent): void {
    const typeHandlers = this.handlers.get(event.type);
    if (typeHandlers) {
      typeHandlers.forEach(handler => {
        try {
          handler(event);
        } catch (e) {
          console.error(`SSE事件处理器异常 [${event.type}]:`, e);
        }
      });
    }
  }

  /**
   * 清理资源
   */
  private cleanup(): void {
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    this.eventSource?.close();
    this.eventSource = null;
  }
}
