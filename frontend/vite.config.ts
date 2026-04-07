import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/app/',
  server: {
    port: 3000,
    proxy: {
      '/graphs': 'http://localhost:8000',
    },
  },
  build: {
    outDir: '../dashboard/static/app',
    emptyOutDir: true,
  },
})
