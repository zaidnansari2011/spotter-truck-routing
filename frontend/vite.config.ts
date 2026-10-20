import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    // In development the Django API runs separately; in production Django serves this build.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'node',
  },
})
