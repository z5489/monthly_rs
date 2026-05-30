import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'serve-data-dir',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          // Serve requests for /data/* from the parent workspace data directory
          if (req.url.startsWith('/data/')) {
            const relativePath = req.url.split('?')[0]; // strip query params
            // Resolve from workspace root (one level up from frontend/)
            const filePath = path.join(__dirname, '..', relativePath);
            if (fs.existsSync(filePath)) {
              if (filePath.endsWith('.json')) {
                res.setHeader('Content-Type', 'application/json');
              } else if (filePath.endsWith('.csv')) {
                res.setHeader('Content-Type', 'text/csv');
              }
              res.end(fs.readFileSync(filePath));
              return;
            }
          }
          next();
        });
      }
    }
  ],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
