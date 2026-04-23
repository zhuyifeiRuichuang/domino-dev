#!/bin/sh
set -e

# =============================================================================
# Domino Frontend — 运行时环境变量注入
# 容器启动时将环境变量内联注入到 index.html
# =============================================================================

HTML_FILE="/usr/share/nginx/html/index.html"
API_URL="${API_URL:-http://localhost:8000}"
DOMINO_DEPLOY_MODE="${DOMINO_DEPLOY_MODE:-docker-compose}"

echo "Injecting runtime environment variables..."
echo "  API_URL = $API_URL"
echo "  DOMINO_DEPLOY_MODE = $DOMINO_DEPLOY_MODE"

# 替换 index.html 中的占位符为实际的环境变量
# 占位符格式: <!-- __DOMINO_ENV__ -->
sed -i "s|<!-- __DOMINO_ENV__ -->|<script>window.__DOMINO_ENV__={API_URL:'$API_URL',DOMINO_DEPLOY_MODE:'$DOMINO_DEPLOY_MODE'};</script>|" "$HTML_FILE"

echo "✅ Runtime env injected successfully"

# 执行 nginx
exec "$@"
