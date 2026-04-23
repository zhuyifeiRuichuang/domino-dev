import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import svgrPlugin from "vite-plugin-svgr";
import viteTsconfigPaths from "vite-tsconfig-paths";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 加载 .env.production 文件
  const env = loadEnv(mode, process.cwd(), "");

  return {
    server: {
      host: "0.0.0.0",
      port: 3000,
    },
    plugins: [
      react(),
      viteTsconfigPaths(),
      svgrPlugin(),
    ],
    build: {
      outDir: "build",
    },
    // 构建时注入环境变量（替代 @import-meta-env）
    define: {
      "import.meta.env.DOMINO_DEPLOY_MODE": JSON.stringify(env.DOMINO_DEPLOY_MODE || "docker-compose"),
      "import.meta.env.API_URL": JSON.stringify(env.API_URL || "http://localhost:8000"),
    },
  };
});
