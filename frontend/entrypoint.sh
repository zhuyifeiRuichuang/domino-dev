#!/bin/sh
set -e

# =============================================================================
# Domino Frontend — 运行时环境变量注入
# 容器启动时从环境变量读取 API_URL，生成 /usr/share/nginx/html/env.js
# 这样 compose.yaml 中的 API_URL 环境变量就能真正生效
# =============================================================================

ENV_JS="/usr/share/nginx/html/env.js"

cat > "$ENV_JS" << EOF
// 运行时环境变量 — 由 entrypoint.sh 在容器启动时生成
window.__DOMINO_ENV__ = {
  API_URL: "${API_URL:-http://localhost:8000}",
  DOMINO_DEPLOY_MODE: "${DOMINO_DEPLOY_MODE:-docker-compose}"
};
EOF

echo "✅ Environment variables injected into env.js:"
echo "   API_URL = ${API_URL:-http:://localhost:8000}"
echo "   DOMINO_DEPLOY_MODE = ${DOMINO_DEPLOY_MODE:-docker-compose}"
