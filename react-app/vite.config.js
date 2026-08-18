import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forwards /api/* calls to the Python backend (api_server.py) during
      // dev, so the browser only ever talks to one origin.
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
