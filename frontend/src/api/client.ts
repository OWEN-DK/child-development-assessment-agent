import axios from 'axios';
import { API_BASE_URL, API_TIMEOUT } from '../lib/constants';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败';
    console.error('[API Error]', message, error.config?.url);
    return Promise.reject(error);
  }
);

export default apiClient;

// 向后兼容导出
export * from './assessment';
export * from './documents';
export * from './knowledge';
export * from './rag-test';
