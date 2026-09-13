import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/scan": "http://127.0.0.1:8002",
      "/health": "http://127.0.0.1:8002",
      "/auth": "http://127.0.0.1:8002",
      "/demo": "http://127.0.0.1:8002",
      "/subscriptions": "http://127.0.0.1:8002",
    },
  },
});
