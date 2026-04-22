# deploy — Domino 部署目录

本目录提供两种部署方式：

| 目录 | 方式 | 适用场景 |
|------|------|----------|
| [`docker/`](./docker/) | Docker Compose | 本地/单机生产部署 |
| [`k8s/`](./k8s/)       | Kubernetes / Helm | 集群生产部署 |

---

## 快速选择

```
单机/本地测试  →  docker/compose.yaml
生产集群      →  k8s/（Helm Chart）
```

---

## Docker 部署

```bash
cd deploy/docker
cp .env.example .env
# 编辑 .env，至少修改以下必填项：
#   DOMINO_DB_PASSWORD, AIRFLOW_DB_PASSWORD,
#   AIRFLOW__CORE__FERNET_KEY, AIRFLOW_ADMIN_PASSWORD

docker compose up -d

# 查看日志
docker compose logs -f domino-rest
```

访问地址：
- 前端：http://localhost:3000
- REST API：http://localhost:8000/docs
- Airflow：http://localhost:8080

详见 [docker/README.md](./docker/README.md)（如有）或 [compose.yaml 注释](./docker/compose.yaml)。

---

## Kubernetes 部署

```bash
helm repo add domino https://tauffer-consulting.github.io/domino/
helm install domino domino/domino --namespace domino --create-namespace \
  --values my-values.yaml --dependency-update
```

详见 [k8s/README.md](./k8s/README.md)。

---

## 镜像构建

所有 Dockerfile 位于 [`../../imageBuild/`](../imageBuild/)，请先构建镜像再部署。

```bash
# 从项目根目录
docker build -f imageBuild/airflow/Dockerfile.prod -t domino-airflow:latest .
docker build -f imageBuild/rest/Dockerfile.prod    -t domino-rest:latest    rest/
docker build -f imageBuild/frontend/Dockerfile.prod -t domino-frontend:latest frontend/
```
