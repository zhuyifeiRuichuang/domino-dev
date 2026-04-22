#!/bin/sh
# =============================================================================
# Domino Frontend — 构建阶段下载工作流示例数据
# 在镜像构建阶段从 GitHub 下载 workflows_gallery 数据并打包为本地静态 JSON
# 容器运行时无需外部网络访问
# =============================================================================

set -e

GALLERY_DIR="public/workflows_gallery"
REPO_BASE="https://raw.githubusercontent.com/Tauffer-Consulting/domino_pieces_gallery/main/workflows_gallery"

echo "[build] Downloading workflow examples from GitHub..."

# 清理并创建目标目录
rm -rf "$GALLERY_DIR"
mkdir -p "$GALLERY_DIR"

# 下载 index.json（包含示例列表和元信息）
echo "[build] Downloading index.json..."
curl -fsSL "${REPO_BASE}/index.json" -o "${GALLERY_DIR}/index.json"

# 解析 index.json 提取所有 jsonFile 文件名，逐个下载
# 使用 node 解析 JSON（构建阶段 node 可用）
node -e "
const fs = require('fs');
const path = require('path');
const https = require('https');

const index = JSON.parse(fs.readFileSync('${GALLERY_DIR}/index.json', 'utf8'));
const base = '${REPO_BASE}';
const dir = '${GALLERY_DIR}';

let done = 0;
const total = index.length;

if (total === 0) {
  console.log('[build] No workflow examples found in index.json');
  process.exit(0);
}

index.forEach((item) => {
  const url = base + '/' + item.jsonFile;
  const dest = path.join(dir, item.jsonFile);

  https.get(url, (res) => {
    if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
      https.get(res.headers.location, (redir) => {
        const file = fs.createWriteStream(dest);
        redir.pipe(file);
        file.on('finish', () => {
          file.close();
          done++;
          console.log('[build] Downloaded (' + done + '/' + total + '): ' + item.jsonFile);
          if (done === total) {
            console.log('[build] All workflow examples downloaded successfully.');
          }
        });
      }).on('error', (err) => {
        console.error('[build] Failed to download ' + item.jsonFile + ': ' + err.message);
        process.exit(1);
      });
    } else {
      const file = fs.createWriteStream(dest);
      res.pipe(file);
      file.on('finish', () => {
        file.close();
        done++;
        console.log('[build] Downloaded (' + done + '/' + total + '): ' + item.jsonFile);
        if (done === total) {
          console.log('[build] All workflow examples downloaded successfully.');
        }
      });
    }
  }).on('error', (err) => {
    console.error('[build] Failed to download ' + item.jsonFile + ': ' + err.message);
    process.exit(1);
  });
});
"

# 确认文件已下载
FILE_COUNT=$(ls -1 "${GALLERY_DIR}"/*.json 2>/dev/null | wc -l)
echo "[build] Workflow gallery: ${FILE_COUNT} JSON files in ${GALLERY_DIR}/"
