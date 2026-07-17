import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: /api/* → FastAPI on :8000, so the front-end calls same-origin
// paths and CORS never enters the picture in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
