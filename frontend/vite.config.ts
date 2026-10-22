import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  build: {
    // MapLibre alone is about 1.07 MB minified (290 KB gzipped) and cannot be split further.
    chunkSizeWarningLimit: 1100,
    rolldownOptions: {
      output: {
        // The map library is most of the bundle and changes far less often than the app, so it
        // gets its own file that browsers keep cached across deploys.
        codeSplitting: {
          groups: [
            { name: 'maplibre', test: /node_modules[\\/]maplibre-gl/ },
            { name: 'mui', test: /node_modules[\\/](@mui|@emotion)/ },
            { name: 'vendor', test: /node_modules/ },
          ],
        },
      },
    },
  },
  server: {
    // In development the Django API runs separately; in production Django serves this build.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'node',
  },
})
