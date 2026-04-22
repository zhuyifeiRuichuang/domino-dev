# imageBuild — Domino 容器镜像构建指南

本目录存放 Domino 各组件的所有 Dockerfile，按组件分子目录组织。
每个子目录均提供 **生产版（`.prod`）** 和 **开发版（`.dev`）** 两种镜像。

---

## 目录结构

```
imageBuild/
├── airflow/            # Airflow + Domino 集成镜像
│   ├── Dockerfile.prod
│   └── Dockerfile.dev
├── rest/               # Domino REST API 服务镜像
│   ├── Dockerfile.prod
│   └── Dockerfile.dev
├── frontend/           # Domino 前端镜像
│   ├── Dockerfile.prod   （多阶段构建：node → nginx）
│   └── Dockerfile.dev    （Vite dev server 热重载）
├── piece/              # Domino Piece 运行时镜像
│   ├── Dockerfile.prod       （CPU，PyPI 安装）
│   ├── Dockerfile.dev        （CPU，可编辑安装）
│   ├── Dockerfile.gpu-prod   （GPU/CUDA，PyPI 安装）
│   └── Dockerfile.gpu-dev    （GPU/CUDA，可编辑安装）
└── README.md
```

---

## 各组件说明

### 1. `airflow/` — Airflow 调度器镜像

| 文件 | 基础镜像 | 用途 |
|------|----------|------|
| `Dockerfile.prod` | `apache/airflow:2.9.3-python3.11` | 生产环境，从 PyPI 安装 `domino-py[airflow]` |
| `Dockerfile.dev`  | `apache/airflow:2.9.3-python3.11` | 开发环境，可编辑安装，配合 volume 热重载 |

**使用的 Airflow 服务：**
- `airflow-webserver`
- `airflow-scheduler`
- `airflow-worker`（Celery）
- `airflow-triggerer`

**构建命令（从项目根目录执行）：**

```bash
# 生产镜像
docker build -f imageBuild/airflow/Dockerfile.prod -t domino-airflow:latest .

# 开发镜像
docker build -f imageBuild/airflow/Dockerfile.dev -t domino-airflow:dev .
```

---

### 2. `rest/` — REST API 服务镜像

| 文件 | 基础镜像 | 用途 |
|------|----------|------|
| `Dockerfile.prod` | `python:3.11-slim` | 生产环境，非 root 用户运行，2 个 worker |
| `Dockerfile.dev`  | `python:3.11-slim` | 开发环境，`--reload` 热重载 |

**构建命令（从 `rest/` 目录执行）：**

```bash
# 生产镜像
docker build -f ../imageBuild/rest/Dockerfile.prod -t domino-rest:latest .

# 开发镜像
docker build -f ../imageBuild/rest/Dockerfile.dev -t domino-rest:dev .
```

> **注意：** `COPY` 路径相对于 `rest/` 目录（build context），因此需在 `rest/` 中执行，或在 compose 中指定 `context: ./rest`。

---

### 3. `frontend/` — 前端静态资源镜像

| 文件 | 基础镜像 | 用途 |
|------|----------|------|
| `Dockerfile.prod` | `node:20-alpine` → `nginx:1.27-alpine` | 多阶段构建，打包后用 nginx 提供静态文件 |
| `Dockerfile.dev`  | `node:20-alpine` | Vite dev server，支持 HMR 热更新 |

**构建命令（从 `frontend/` 目录执行）：**

```bash
# 生产镜像
docker build -f ../imageBuild/frontend/Dockerfile.prod -t domino-frontend:latest .

# 开发镜像
docker build -f ../imageBuild/frontend/Dockerfile.dev -t domino-frontend:dev .
```

**生产镜像特性：**
- nginx 配置支持 React Router（History API）
- 静态资源（JS/CSS/图片）设置 1 年强缓存

---

### 4. `piece/` — Piece 运行时镜像

Piece 镜像用于 **Airflow Worker 运行单个 Piece 任务**，与 Airflow 调度器独立，可按需定制依赖。

| 文件 | 基础镜像 | GPU | 用途 |
|------|----------|-----|------|
| `Dockerfile.prod`     | `python:3.11-slim`                   | ✗ | 生产，CPU，PyPI 安装 |
| `Dockerfile.dev`      | `python:3.11-slim`                   | ✗ | 开发，CPU，可编辑安装 |
| `Dockerfile.gpu-prod` | `nvidia/cuda:12.3.1-base-ubuntu22.04` | ✓ | 生产，GPU/CUDA 12.3 |
| `Dockerfile.gpu-dev`  | `nvidia/cuda:12.3.1-base-ubuntu22.04` | ✓ | 开发，GPU，可编辑安装 |

**目录约定（镜像内）：**

| 目录 | 说明 |
|------|------|
| `/home/domino/pieces_repository` | Piece 代码挂载点 |
| `/home/run_data` | 运行时数据输出目录 |
| `/airflow/xcom/return.json` | Airflow XCom sidecar 通信文件 |

**构建命令（从项目根目录执行）：**

```bash
# CPU 生产镜像
docker build -f imageBuild/piece/Dockerfile.prod -t domino-piece:latest .

# CPU 开发镜像
docker build -f imageBuild/piece/Dockerfile.dev -t domino-piece:dev .

# GPU 生产镜像（需要 NVIDIA Container Toolkit）
docker build -f imageBuild/piece/Dockerfile.gpu-prod -t domino-piece:gpu-latest .

# GPU 开发镜像
docker build -f imageBuild/piece/Dockerfile.gpu-dev -t domino-piece:gpu-dev .
```

---

## 安全说明

1. **固定基础镜像版本** — 所有 Dockerfile 均使用具体版本号（如 `python:3.11-slim`），避免意外升级破坏构建。
2. **最小化系统包** — 使用 `--no-install-recommends` 减少攻击面。
3. **清理 apt 缓存** — 每个 `apt-get` 后执行 `rm -rf /var/lib/apt/lists/*` 减小镜像体积。
4. **非 root 用户** — `rest/Dockerfile.prod` 和 `frontend/Dockerfile.prod` 均创建专用系统用户运行服务。
5. **CUDA 版本升级** — GPU 镜像从旧版 CUDA 11.8 升级至 12.3.1，修复历史版本中的已知 CVE。

---

## 版本矩阵

| 组件 | Python | Airflow | CUDA |
|------|--------|---------|------|
| airflow | 3.11 | 2.9.3 | — |
| rest | 3.11 | — | — |
| frontend | Node 20 | — | — |
| piece (CPU) | 3.11 | — | — |
| piece (GPU) | 3.11 | — | 12.3.1 |
