import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const VM = "https://linkguessr.duckdns.org";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // Même relais qu'en production (vercel.json) : /v1 -> API de la VM, /umami -> Umami.
    proxy: {
      "/v1": { target: VM, changeOrigin: true, rewrite: (p) => p.replace(/^\/v1/, "") },
      "/umami": { target: VM, changeOrigin: true },
    },
  },
});
