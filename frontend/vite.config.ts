import { defineConfig } from 'vite'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export default defineConfig({
    build: {
        // Output compiled assets to the Flask static folder
        outDir: '../serp-to-context-api/app/static/dist',
        emptyOutDir: true,

        // Generate manifest for easier asset linking (optional, but good practice)
        manifest: true,

        rollupOptions: {
            // Use main.ts as the entry point
            input: resolve(__dirname, 'src/main.ts'),

            output: {
                // Ensure consistent naming for easier manual linking if not using manifest
                entryFileNames: 'assets/[name].js',
                chunkFileNames: 'assets/[name].js',
                assetFileNames: 'assets/[name].[ext]'
            }
        }
    }
})
