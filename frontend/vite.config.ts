import importMetaEnv from "@import-meta-env/unplugin";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import svgrPlugin from "vite-plugin-svgr";
import viteTsconfigPaths from "vite-tsconfig-paths";

// https://vitejs.dev/config/
export default defineConfig({
  root: __dirname,  // 显式指定根目录为 frontend/
  server: {
    host: "0.0.0.0",
    port: 3000,
  },
  plugins: [
    react(),
    viteTsconfigPaths(),
    svgrPlugin(),
    importMetaEnv.vite({ example: ".env.production" }),
  ],
  build: {
    outDir: "build",
  },
});
