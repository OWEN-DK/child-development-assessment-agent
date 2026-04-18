import { message } from 'antd';

export interface ApiError {
  message: string;
  code?: number;
  error_code?: string;
  details?: unknown;
}

export function extractApiError(error: unknown): ApiError {
  if (error instanceof Error) {
    return {
      message: (error as any).message || error.message,
      code: (error as any).code,
      error_code: (error as any).error_code,
      details: (error as any).details,
    };
  }
  return { message: '未知错误' };
}

export async function handleApiCall<T>(
  fn: () => Promise<T>,
  options?: {
    successMsg?: string;
    errorMsg?: string;
    onSuccess?: (data: T) => void;
    silent?: boolean;
  }
): Promise<T | null> {
  try {
    const data = await fn();
    if (options?.successMsg && !options?.silent) {
      message.success(options.successMsg);
    }
    options?.onSuccess?.(data);
    return data;
  } catch (error) {
    const apiError = extractApiError(error);
    if (options?.errorMsg && !options?.silent) {
      message.error(options.errorMsg);
    } else if (!options?.silent) {
      message.error(apiError.message);
    }
    return null;
  }
}

export async function withNotification<T>(
  fn: () => Promise<T>,
  options: { successMsg?: string; errorMsg?: string } = {}
): Promise<T> {
  try {
    const result = await fn();
    if (options.successMsg) {
      message.success(options.successMsg);
    }
    return result;
  } catch (error) {
    const apiError = extractApiError(error);
    const errorMsg = options.errorMsg || apiError.message;
    message.error(errorMsg);
    throw error;
  }
}

export const notification = {
  success: (msg: string, duration?: number) => message.success(msg, duration),
  error: (msg: string, duration?: number) => message.error(msg, duration),
  warning: (msg: string, duration?: number) => message.warning(msg, duration),
  info: (msg: string, duration?: number) => message.info(msg, duration),
  withNotification,
  extractApiError,
};
