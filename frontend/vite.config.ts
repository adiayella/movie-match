import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Allow Cloudflare Quick Tunnel hosts (random subdomain each run) so the
    // app can be reached from devices where LAN access is blocked by
    // network-level client isolation (common on office/campus WiFi).
    allowedHosts: [".trycloudflare.com"],
    // Proxy the API through the dev server so the app is single-origin.
    // Two wins that matter over a flaky/rate-limited tunnel: no CORS
    // preflight (every POST was sending an extra OPTIONS round trip, i.e.
    // double the requests), and only one tunnel to keep alive instead of
    // two. Quick tunnels throttle -- they were returning 530s mid-session.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
