import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: true,
    server: {
      deps: {
        inline: [/@adobe/, /@react-spectrum/, /@spectrum-icons/],
      },
    },
  },
});
