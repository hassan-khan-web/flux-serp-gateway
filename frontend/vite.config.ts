import { defineConfig } from 'vite'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export default defineConfig({
    server: {
        host: true, // Listen on all addresses, including LAN and public addresses
        port: 5173,
        strictPort: true, // Fail if port is already in use
        proxy: {
            // Proxy API requests to the backend container
            '/search': {
                target: 'http://api:8000',
                changeOrigin: true,
                secure: false,
            },
            '/tasks': {
                target: 'http://api:8000',
                changeOrigin: true,
                secure: false,
            },
            '/health': {
                target: 'http://api:8000',
                changeOrigin: true,
                secure: false,
            }
        }
    },
    build: {
        outDir: '../serp-to-context-api/app/static/dist',
        emptyOutDir: true,
        manifest: true,
        rollupOptions: {
            input: resolve(__dirname, 'src/main.ts'),
            output: {
                entryFileNames: 'assets/[name].js',
                chunkFileNames: 'assets/[name].js',
                assetFileNames: 'assets/[name].[ext]'
            }
        }
    }
})
