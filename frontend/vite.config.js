import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'fs'

const configPath = new URL('../config/config.json', import.meta.url).pathname
const rawConfig = JSON.parse(readFileSync(configPath, 'utf-8'))
const backendPort = rawConfig.backend?.port || 8000
const frontendPort = rawConfig.frontend?.port || 5173

export default defineConfig({
  plugins: [vue()],
  server: {
    port: frontendPort,
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
      '/static': {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      }
    }
  }
})
