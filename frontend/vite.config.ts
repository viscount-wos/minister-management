import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // One chunk per language (all its namespaces): a player downloads only the
        // language they use (src/i18n/index.ts loads it on demand).
        manualChunks(id) {
          const m = id.match(/[\\/]i18n[\\/]locales[\\/]([a-z]{2})[\\/][^\\/]+\.json/)
          if (m) return `locale-${m[1]}`
          return undefined
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true
      }
    }
  }
})
