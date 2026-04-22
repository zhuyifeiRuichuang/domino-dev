#!/bin/sh
# =============================================================================
# Domino Frontend — 运行时环境变量注入
# 在 nginx 启动前，通过 import-meta-env 将环境变量注入到 index.html
# =============================================================================

set -e

# 生成 .env.production 文件供 import-meta-env 使用
ENV_FILE="/usr/share/nginx/html/.env.production"
echo "DOMINO_DEPLOY_MODE=${DOMINO_DEPLOY_MODE:-local-compose}" > "$ENV_FILE"
echo "API_URL=${API_URL:-http://domino-rest:8000}" >> "$ENV_FILE"

# 使用 import-meta-env 注入环境变量到 index.html
/usr/share/nginx/html/import-meta-env \
    -x "$ENV_FILE" \
    -p /usr/share/nginx/html/index.html \
    2>/dev/null || true

echo "[domino-frontend] Environment variables injected successfully."
echo "[domino-frontend] API_URL=${API_URL:-http://domino-rest:8000}"
