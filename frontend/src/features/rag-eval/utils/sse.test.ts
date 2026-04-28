import { describe, it, expect, vi, afterEach } from 'vitest';
import { createSSEConnection, parseSSEEvent } from './sse';

/** 创建模拟 ReadableStream，依次输出指定文本块 */
function createMockStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

import type { SSECallbacks } from './sse';

/** 创建一组 mock 回调，类型与 SSECallbacks 兼容 */
function createMockCallbacks(): SSECallbacks {
  return {
    onOpen: vi.fn<() => void>(),
    onMessage: vi.fn<(raw: string) => void>(),
    onError: vi.fn<() => void>(),
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('createSSEConnection', () => {
  it('响应成功时调用 onOpen 并读取流中消息', async () => {
    const callbacks = createMockCallbacks();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      body: createMockStream([
        'data: {"type":"progress","data":{"pct":50}}\n\n',
        'data: {"type":"done","data":{}}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', mockFetch);

    const controller = new AbortController();
    await createSSEConnection('/api/sse', controller.signal, callbacks);

    expect(callbacks.onOpen).toHaveBeenCalledTimes(1);
    expect(callbacks.onMessage).toHaveBeenCalledTimes(2);
    expect(callbacks.onMessage).toHaveBeenNthCalledWith(
      1,
      '{"type":"progress","data":{"pct":50}}',
    );
    expect(callbacks.onMessage).toHaveBeenNthCalledWith(
      2,
      '{"type":"done","data":{}}',
    );

    vi.unstubAllGlobals();
  });

  it('响应非 ok 时调用 onError', async () => {
    const callbacks = createMockCallbacks();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    });
    vi.stubGlobal('fetch', mockFetch);

    const controller = new AbortController();
    await createSSEConnection('/api/sse', controller.signal, callbacks);

    expect(callbacks.onError).toHaveBeenCalledTimes(1);
    expect(callbacks.onOpen).not.toHaveBeenCalled();
    expect(callbacks.onMessage).not.toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it('fetch 抛出异常时调用 onError', async () => {
    const callbacks = createMockCallbacks();
    const mockFetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', mockFetch);

    const controller = new AbortController();
    await createSSEConnection('/api/sse', controller.signal, callbacks);

    expect(callbacks.onError).toHaveBeenCalledTimes(1);
    expect(callbacks.onOpen).not.toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it('解析单个块中的多条 data: 行', async () => {
    const callbacks = createMockCallbacks();
    const multiLineChunk =
      'data: {"a":1}\n\ndata: {"b":2}\n\ndata: {"c":3}\n\n';
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      body: createMockStream([multiLineChunk]),
    });
    vi.stubGlobal('fetch', mockFetch);

    const controller = new AbortController();
    await createSSEConnection('/api/sse', controller.signal, callbacks);

    expect(callbacks.onMessage).toHaveBeenCalledTimes(3);
    expect(callbacks.onMessage).toHaveBeenNthCalledWith(1, '{"a":1}');
    expect(callbacks.onMessage).toHaveBeenNthCalledWith(2, '{"b":2}');
    expect(callbacks.onMessage).toHaveBeenNthCalledWith(3, '{"c":3}');

    vi.unstubAllGlobals();
  });

  it('AbortSignal 中止后停止读取', async () => {
    const callbacks = createMockCallbacks();
    const controller = new AbortController();
    controller.abort();

    const mockFetch = vi.fn().mockRejectedValue(new DOMException('Aborted', 'AbortError'));
    vi.stubGlobal('fetch', mockFetch);

    await createSSEConnection('/api/sse', controller.signal, callbacks);

    expect(callbacks.onError).toHaveBeenCalledTimes(1);
    expect(callbacks.onOpen).not.toHaveBeenCalled();
    expect(callbacks.onMessage).not.toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it('处理跨块的残行（buffer 缓冲逻辑）', async () => {
    const callbacks = createMockCallbacks();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      body: createMockStream([
        'data: {"type":"pro',
        'gress","pct":50}\n\ndata: {"type":"done"}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', mockFetch);

    const controller = new AbortController();
    await createSSEConnection('/api/sse', controller.signal, callbacks);

    expect(callbacks.onOpen).toHaveBeenCalledTimes(1);
    expect(callbacks.onMessage).toHaveBeenCalledTimes(2);
    expect(callbacks.onMessage).toHaveBeenNthCalledWith(
      1,
      '{"type":"progress","pct":50}',
    );
    expect(callbacks.onMessage).toHaveBeenNthCalledWith(2, '{"type":"done"}');

    vi.unstubAllGlobals();
  });
});

describe('parseSSEEvent', () => {
  it('解析有效 JSON 返回结构化对象', () => {
    const result = parseSSEEvent('{"type":"progress","data":{"pct":50}}');
    expect(result).toEqual({ type: 'progress', data: { pct: 50 } });
  });

  it('无效 JSON 返回 type=unknown 且 data 为原始字符串', () => {
    const result = parseSSEEvent('not-json');
    expect(result).toEqual({ type: 'unknown', data: 'not-json' });
  });

  it('空字符串返回 type=unknown 且 data 为空字符串', () => {
    const result = parseSSEEvent('');
    expect(result).toEqual({ type: 'unknown', data: '' });
  });
});
