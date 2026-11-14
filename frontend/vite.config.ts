import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Backend (FastAPI/uvicorn) the dev server proxies to. Override with
// OMNI_BACKEND if the API runs somewhere other than the documented default.
const BACKEND = process.env.OMNI_BACKEND ?? 'http://localhost:8080'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      // REST endpoints.
      '/api': { target: BACKEND, changeOrigin: false },
      // Server-Sent Events live feed — keep the connection open/streamed.
      '/events': { target: BACKEND, changeOrigin: false },
      // OAuth redirect callbacks (Spotify) land on the FastAPI app, not the SPA.
      '/oauth': { target: BACKEND, changeOrigin: false },
    },
  },
})
