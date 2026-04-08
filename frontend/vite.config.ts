import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 参考 https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        // 全局自动引入设计 tokens
        additionalData: `@use "@/styles/tokens.scss" as *;`
      }
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // 开发环境代理后端
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    // 对应宪法性能门禁：首屏 JS gzip < 250KB
    chunkSizeWarningLimit: 500
  }
})
