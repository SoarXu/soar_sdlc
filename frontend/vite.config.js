import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

if (process.env.VITE_RELEASE_BUILD === '1' && (!process.env.VITE_APP_VERSION || !process.env.VITE_GIT_COMMIT)) {
  throw new Error('Release build requires VITE_APP_VERSION and VITE_GIT_COMMIT')
}

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
