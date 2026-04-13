/// <reference types="vitest" />
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 加载对应环境的环境变量
  const env = loadEnv(mode, process.cwd(), '')
  return {
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
    deps: {
      inline: ['@ant-design/pro-components'],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        api: 'modern-compiler',
      },
    },
  },
  server: {
    host: env.VITE_DEV_SERVER_HOST || '127.0.0.1',
    port: Number(env.VITE_DEV_SERVER_PORT) || 5173,
    proxy: {
      '/assess': {
        target: env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // 匹配所有/rag/开头的API路径，不会匹配前端路由/rag-evaluation
      '^/rag/': {
        target: env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/api': {
        target: env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  }
})
