import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    fs: { allow: ['..', '/common'] },
    port: 5173,
    strictPort: true,
    watch: { usePolling: true },
    proxy: { '/api': 'http://backend:8000' },
  },
});
