import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // 개발 중 CORS 문제를 백엔드 미들웨어 없이 해결하기 위한 프록시.
      // 프론트(:5173) -> /api 요청을 백엔드(:8000)로 그대로 전달한다.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
