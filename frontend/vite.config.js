import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend origin: docker-compose sets BACKEND_URL=http://backend:8000;
// local dev defaults to localhost.
const target = process.env.BACKEND_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: { '/api': { target, changeOrigin: true } },
  },
})
