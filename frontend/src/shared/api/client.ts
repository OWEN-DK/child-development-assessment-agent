import axios from 'axios';
import qs from 'qs';
import { API_BASE_URL, API_TIMEOUT } from '@shared/lib/constants';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
  paramsSerializer: (params) => {
    return qs.stringify(params, { arrayFormat: 'repeat' });
  },
});

apiClient.interceptors.request.use(
  (config) => {
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => {
    // blob 响应直接透传，不做 JSON 解包
    if (response.config.responseType === 'blob') {
      return response;
    }

    // 解包统一响应格式 {code, message, data}
    const { code, message: msg, data } = response.data;
    
    if (code === 0) {
      // 成功响应，返回 data 字段中的业务数据
      response.data = data;
      return response;
    }
    
    // 业务错误（HTTP 200 但 code !== 0）
    const error = new Error(msg || '请求失败');
    (error as any).code = code;
    (error as any).error_code = response.data.error_code;
    (error as any).details = response.data.details;
    return Promise.reject(error);
  },
  (error) => {
    // HTTP 错误处理（4xx/5xx）
    const responseData = error.response?.data;
    
    if (responseData) {
      // 优先使用后端返回的错误信息
      const errorMsg = responseData.message || responseData.detail || error.message;
      const errorCode = responseData.error_code || '';
      const details = responseData.details || null;
      
      console.error(
        `[API Error] code=${responseData.code || error.response?.status}, error_code=${errorCode}`,
        errorMsg,
        details,
        error.config?.url
      );
      
      error.message = errorMsg;
      error.code = responseData.code;
      error.error_code = errorCode;
      error.details = details;
    } else {
      console.error('[API Error]', error.message, error.config?.url);
    }
    
    return Promise.reject(error);
  }
);

export default apiClient;
