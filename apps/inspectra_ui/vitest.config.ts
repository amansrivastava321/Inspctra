import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    exclude: ['e2e/**', 'node_modules/**'],
    // Page-level tests render large trees in jsdom. The 5s default is tight for a loaded CI runner
    // (one test was killed at 5.3s there while taking ~1.5s locally). Healthy tests are unaffected;
    // this only changes how long a genuinely hung test waits. Keep it above asyncUtilTimeout (setup.ts).
    testTimeout: 20000,
    hookTimeout: 20000,
  },
})
