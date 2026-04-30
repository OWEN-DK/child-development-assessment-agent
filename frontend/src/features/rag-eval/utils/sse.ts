/**
 * SSE 连接配置回调
 */
export interface SSECallbacks {
  /** 连接成功建立时触发 */
  onOpen: () => void;
  /** 收到一条完整 SSE 消息时触发（`data:` 行后的原始字符串） */
  onMessage: (raw: string) => void;
  /** 连接异常或中断时触发 */
  onError: () => void;
}

/**
 * 建立 fetch-based SSE 连接
 *
 * 原生 EventSource 不支持自定义请求头（如 Authorization token），
 * 因此使用 fetch + ReadableStream 手动解析 SSE 协议。
 *
 * @param url   - SSE 端点 URL
 * @param signal - AbortSignal，用于外部取消连接
 * @param callbacks - 生命周期回调
 */
export async function createSSEConnection(
  url: string,
  signal: AbortSignal,
  callbacks: SSECallbacks,
): Promise<void> {
  try {
    const response = await fetch(url, {
      signal,
      headers: { Accept: 'text/event-stream' },
    });

    if (!response.ok) {
      callbacks.onError();
      return;
    }

    callbacks.onOpen();

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          callbacks.onMessage(line.slice(6));
        }
      }
    }
  } catch {
    callbacks.onError();
  }
}

/**
 * 解析 SSE `data:` 字段为结构化对象
 */
export function parseSSEEvent(raw: string): { type: string; data: unknown } {
  try {
    return JSON.parse(raw);
  } catch {
    return { type: 'unknown', data: raw };
  }
}
