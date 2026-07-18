import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // The Python report server owns the data; proxy so the web app can
    // fetch /api/* same-origin in dev.
    proxy: {
      "/api": "http://127.0.0.1:5177",
    },
  },
});
