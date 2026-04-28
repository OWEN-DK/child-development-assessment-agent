import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useSSEProgress } from './useSSEProgress';
import { createSSEConnection } from '../utils/sse';

vi.mock('../utils/sse', () => ({
  createSSEConnection: vi.fn(),
}));

const mockCreateConnection = vi.mocked(createSSEConnection);

afterEach(() => {
  vi.restoreAllMocks();
  mockCreateConnection.mockReset();
});

describe('useSSEProgress', () => {
  it('url 为 null 时 status 为 connecting 且 events 为空', () => {
    const { result } = renderHook(() => useSSEProgress(null));

    expect(result.current.status).toBe('connecting');
    expect(result.current.events).toEqual([]);
  });

  it('url 存在时调用 createSSEConnection', () => {
    mockCreateConnection.mockImplementation(async () => {});

    renderHook(() => useSSEProgress('/api/sse'));

    expect(mockCreateConnection).toHaveBeenCalledTimes(1);
    expect(mockCreateConnection).toHaveBeenCalledWith(
      '/api/sse',
      expect.any(AbortSignal),
      expect.objectContaining({
        onOpen: expect.any(Function),
        onMessage: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
  });

  it('收到终结事件时 status 设为 done', async () => {
    let capturedCallbacks: Parameters<typeof createSSEConnection>[2] | null = null;
    mockCreateConnection.mockImplementation(
      async (_url: string, _signal: AbortSignal, callbacks: Parameters<typeof createSSEConnection>[2]) => {
        capturedCallbacks = callbacks;
      },
    );

    const { result } = renderHook(() => useSSEProgress('/api/sse'));

    await waitFor(() => {
      expect(capturedCallbacks).not.toBeNull();
    });

    capturedCallbacks!.onOpen();

    await waitFor(() => {
      expect(result.current.status).toBe('connected');
    });

    capturedCallbacks!.onMessage(
      JSON.stringify({ type: 'run_completed', data: { result: 'ok' } }),
    );

    await waitFor(() => {
      expect(result.current.status).toBe('done');
    });

    expect(result.current.events).toEqual([
      { type: 'run_completed', data: { result: 'ok' } },
    ]);
  });

  it('累积 onMessage 回调中的全部事件', async () => {
    let capturedCallbacks: Parameters<typeof createSSEConnection>[2] | null = null;
    mockCreateConnection.mockImplementation(
      async (_url: string, _signal: AbortSignal, callbacks: Parameters<typeof createSSEConnection>[2]) => {
        capturedCallbacks = callbacks;
      },
    );

    const { result } = renderHook(() => useSSEProgress('/api/sse'));

    await waitFor(() => {
      expect(capturedCallbacks).not.toBeNull();
    });

    capturedCallbacks!.onMessage(
      JSON.stringify({ type: 'progress', data: { pct: 10 } }),
    );
    capturedCallbacks!.onMessage(
      JSON.stringify({ type: 'progress', data: { pct: 50 } }),
    );
    capturedCallbacks!.onMessage(
      JSON.stringify({ type: 'progress', data: { pct: 90 } }),
    );

    await waitFor(() => {
      expect(result.current.events).toHaveLength(3);
    });

    expect(result.current.events).toEqual([
      { type: 'progress', data: { pct: 10 } },
      { type: 'progress', data: { pct: 50 } },
      { type: 'progress', data: { pct: 90 } },
    ]);
  });

  it('onError 触发时 status 设为 error', async () => {
    let capturedCallbacks: Parameters<typeof createSSEConnection>[2] | null = null;
    mockCreateConnection.mockImplementation(
      async (_url: string, _signal: AbortSignal, callbacks: Parameters<typeof createSSEConnection>[2]) => {
        capturedCallbacks = callbacks;
      },
    );

    const { result } = renderHook(() => useSSEProgress('/api/sse'));

    await waitFor(() => {
      expect(capturedCallbacks).not.toBeNull();
    });

    capturedCallbacks!.onError();

    await waitFor(() => {
      expect(result.current.status).toBe('error');
    });
  });

  it('url 变为空字符串时不再发起新连接', async () => {
    mockCreateConnection.mockImplementation(async () => {});

    const { rerender, unmount } = renderHook(
      ({ url }: { url: string | null }) => useSSEProgress(url),
      { initialProps: { url: '/api/sse' } },
    );

    expect(mockCreateConnection).toHaveBeenCalledTimes(1);

    rerender({ url: null });

    expect(mockCreateConnection).toHaveBeenCalledTimes(1);

    unmount();
  });
});
