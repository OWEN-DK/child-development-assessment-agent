import { message } from 'antd';

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
    if (options?.errorMsg && !options?.silent) {
      message.error(options.errorMsg);
    }
    return null;
  }
}

export const notification = {
  success: (msg: string, duration?: number) => message.success(msg, duration),
  error: (msg: string, duration?: number) => message.error(msg, duration),
  warning: (msg: string, duration?: number) => message.warning(msg, duration),
  info: (msg: string, duration?: number) => message.info(msg, duration),
};