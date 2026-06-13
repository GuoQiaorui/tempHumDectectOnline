import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue(),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000', // ✅ 关键：必须用 ws://
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/(ws|api)/, '/$1'),
      },
    },
  },
})