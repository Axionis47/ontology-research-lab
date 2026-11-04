import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: process.env.OAK_API_URL ?? "http://127.0.0.1:8501",
        changeOrigin: false,
      },
    },
  },
  build: {
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          graph: ["@xyflow/react", "@dagrejs/dagre"],
          ui: ["@radix-ui/react-dialog"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
});
