import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Seccion 12 del plan: React + TypeScript + Vite.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
