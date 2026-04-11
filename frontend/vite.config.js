import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy API calls to FastAPI backend
    proxy: {
      '/api': 'http://localhost:8000',
      '/analyze-frame': 'http://localhost:8000',
      '/process-text': 'http://localhost:8000',
      '/predict-age': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
