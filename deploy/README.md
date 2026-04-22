# deploy — Domino 部署目录

本目录提供三种部署方式：

| 目录 | 方式 | 适用场景 |
|------|------|----------|
| [`docker/`](./docker/) | Docker Compose | 本地/单机生产部署 |
| [`k8s/`](./k8s/)       | Kubernetes / Helm | 集群生产部署 |
| — | 主机环境 | 直接在宿主机运行（非容器化） |

---

## 快速选择

```
快速测试/本地开发  →  docker/compose.yaml
生产集群部署      →  k8s/（Helm Chart）
裸机/无容器环境   →  主机环境部署
```

---

## 1. Docker Compose 部署

```bash
cd deploy/docker
cp .env.example .env
# 编辑 .env，至少修改以下必填项：
#   DOMINO_DB_PASSWORD, AIRFLOW_DB_PASSWORD,
#   AIRFLOW__CORE__FERNET_KEY, AIRFLOW_ADMIN_PASSWORD

# 自动构建镜像并启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f domino-rest
```

访问地址：
- 前端：http://localhost:3000
- REST API：http://localhost:8000/docs
- Airflow：http://localhost:8080

---

## 2. Kubernetes 部署

```bash
helm repo add domino https://tauffer-consulting.github.io/domino/
helm install domino domino/domino --namespace domino --create-namespace \
  --values my-values.yaml --dependency-update
```

详见 [k8s/README.md](./k8s/README.md)。

---

## 3. 主机环境部署

适用于无 Docker/Kubernetes 环境的裸机部署，或需要直接调试的场景。

Piece 代码直接从宿主机运行，通过环境变量配置执行参数。

详见项目文档。

---

## 镜像构建（可选）

Docker Compose 部署时会自动构建镜像。如需手动构建：

```bash
# 从项目根目录执行
docker build -f imageBuild/airflow/Dockerfile.prod -t domino-airflow:latest .
docker build -f imageBuild/rest/Dockerfile.prod    -t domino-rest:latest    .
docker build -f imageBuild/frontend/Dockerfile.prod -t domino-frontend:latest .
```

所有 Dockerfile 位于 [`../../imageBuild/`](../imageBuild/)。
