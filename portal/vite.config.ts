import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Allow reverse-proxied public hostnames (e.g. ops.buruujfintech.com)
    allowedHosts: true,
    proxy: {
      // Local default; Docker Compose sets VITE_PROXY_TARGET=http://api:8000
      "/api": process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
      "/health": process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
    },
  },
});
