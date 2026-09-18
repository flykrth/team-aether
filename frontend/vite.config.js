import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
// The dev proxy is only used when VITE_API_BASE_URL is empty. It targets the backend's documented default
// port (8000); if the backend runs elsewhere (e.g. uvicorn on 8080) set VITE_PROXY_TARGET in frontend/.env.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const target = env.VITE_PROXY_TARGET || 'http://localhost:8000';
  const proxied = { target, changeOrigin: true };
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { '/api': proxied, '/cds-services': proxied, '/health': proxied },
    },
  };
});
