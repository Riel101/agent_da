import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ command }) => {
  // A Render static build without this bakes `http://localhost:8000` into the
  // bundle and ships a UI that can never reach the API. Fail the deploy instead.
  if (command === 'build' && process.env.RENDER && !process.env.VITE_API_URL) {
    throw new Error(
      'VITE_API_URL is required for a Render static build (e.g. https://agent-da-api.onrender.com/api/v1)',
    )
  }

  return {
    plugins: [react(), tailwindcss()],
    server: { port: 5173 },
  }
})
