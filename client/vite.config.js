import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': { target: 'http://localhost:5001', changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') },
      '/socket.io': {
        target: 'http://localhost:5001',
        ws: true,
        configure: (proxy) => {
          proxy.on('error', (err, _req, _res) => {
            if (err.code === 'EPIPE' || err.code === 'ECONNRESET') {
              // Backend restarted or not running; socket closed. Client will reconnect. Skip noisy log.
              return
            }
            console.error('[vite] ws proxy error:', err.message)
          })
        },
      },
    },
  },
})
