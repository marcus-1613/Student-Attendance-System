import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    // 开发期代理：把 /api 和 /face-images 转发到后端 8000。
    // - /api         ：后端 REST 接口
    // - /face-images ：后端静态挂载的脸照图片目录（image_path 拼 /face-images 前缀访问）
    // 这样前端可以用相对路径请求，规避跨域，也方便将来 WebSocket 代理（ws:true）。
    // 注意：图片代理前缀刻意用 /face-images 而非 /faces，避开前端路由 /faces
    // （人脸录入页），否则访问页面时会被代理误判转发到后端，页面空白。
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/face-images': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // WebSocket 公告推送通道：必须显式 ws:true，否则前端连
      // ws://127.0.0.1:5173/ws/notices 会静默失败（Vite 不会转发升级请求）。
      '/ws': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
