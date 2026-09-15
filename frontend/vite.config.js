import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/frontend/',
  server: {
    proxy: {
      '/api': {
        target: 'http://35.237.89.149',
        changeOrigin: true
      }
    }
  }
});
