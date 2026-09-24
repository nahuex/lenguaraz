// SPDX-License-Identifier: Apache-2.0
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// During development the Vite dev server proxies API, health and WebSocket
// traffic to the Lenguaraz backend. In production the backend serves `dist/`.
const BACKEND = 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': BACKEND,
      '/healthz': BACKEND,
      '/ws': { target: BACKEND, ws: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    globals: true,
    css: false,
  },
});
