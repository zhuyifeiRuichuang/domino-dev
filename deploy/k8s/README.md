# Domino Kubernetes 部署指南

Domino 官方支持通过 **Helm Chart** 部署到 Kubernetes 集群。
Helm Chart 源码位于项目根目录 [`helm/domino/`](../../helm/domino/)。

---

## 部署方式

Domino 支持三种标准部署模式：

| 部署模式 | 说明 |
|----------|------|
| **host** | 主机环境部署（直接在宿主机运行 Piece） |
| **docker-compose** | Docker Compose 部署（单机/本地生产环境） |
| **k8s** | Kubernetes 部署（集群生产环境） |

---

## 前置条件

| 工具 | 最低版本 | 说明 |
|------|---------|------|
| kubectl | 1.25+ | 连接 Kubernetes 集群 |
| helm | 3.12+ | 安装/管理 chart |
| Kubernetes | 1.25+ | 集群版本 |

---

## 快速部署（Helm）

### 1. 添加 Domino Helm 仓库

```bash
helm repo add domino https://tauffer-consulting.github.io/domino/
helm repo update
```

### 2. 自定义配置

将默认 values 导出并修改：

```bash
helm show values domino/domino > my-values.yaml
# 编辑 my-values.yaml，修改镜像、密钥等配置
```

关键配置项（`my-values.yaml`）：

```yaml
# REST 服务
dominoRest:
  image:
    repository: your-registry/domino-rest
    tag: latest
  env:
    DOMINO_DEPLOY_MODE: "k8s"
    DOMINO_WORKFLOW_STORAGE_MODE: "git"   # k8s 推荐 git 模式
    DOMINO_WORKFLOWS_GIT_REPO_URL: "https://github.com/your-org/workflows"
    DOMINO_WORKFLOWS_GIT_TOKEN: "ghp_xxx"
    GIT_TOKEN_SECRET_KEY: "your-fernet-key"

# 前端
dominoFrontend:
  image:
    repository: your-registry/domino-frontend
    tag: latest

# Airflow（使用官方 Apache Airflow Helm Chart 作为依赖）
airflow:
  executor: KubernetesExecutor   # k8s 推荐 KubernetesExecutor
  images:
    airflow:
      repository: your-registry/domino-airflow
      tag: latest
```

### 3. 安装

```bash
# 安装（含 Airflow 依赖）
helm install domino domino/domino \
  --namespace domino \
  --create-namespace \
  --values my-values.yaml \
  --dependency-update

# 查看部署状态
kubectl get pods -n domino -w
```

### 4. 访问服务

```bash
# 查看 Service 外部地址
kubectl get svc -n domino

# 临时端口转发（开发调试）
kubectl port-forward svc/domino-rest 8000:8000 -n domino
kubectl port-forward svc/domino-frontend 3000:80 -n domino
kubectl port-forward svc/airflow-webserver 8080:8080 -n domino
```

---

## 使用本地 Helm Chart 部署

如果需要使用项目内的 Helm Chart（适合二次开发）：

```bash
# 从项目根目录执行
helm install domino ./helm/domino \
  --namespace domino \
  --create-namespace \
  --values my-values.yaml \
  --dependency-update
```

---

## 更新/升级

```bash
helm upgrade domino domino/domino \
  --namespace domino \
  --values my-values.yaml \
  --dependency-update
```

---

## 卸载

```bash
helm uninstall domino --namespace domino
# 可选：删除 PVC（数据库数据）
kubectl delete pvc --all -n domino
```

---

## 生产部署建议

1. **存储模式**：k8s 环境推荐使用 `DOMINO_WORKFLOW_STORAGE_MODE=git`，避免节点间文件共享问题。
2. **Executor**：使用 `KubernetesExecutor`，每个 Task 独立 Pod，隔离性更好。
3. **镜像仓库**：将镜像推送到私有仓库（如 Harbor、AWS ECR、阿里云 ACR）并配置 `imagePullSecrets`。
4. **密钥管理**：使用 Kubernetes Secret 或 HashiCorp Vault 管理 `GIT_TOKEN_SECRET_KEY`、数据库密码等敏感配置。
5. **Ingress**：配置 Ingress Controller（nginx/traefik）对外暴露前端和 REST API，推荐 TLS 终止。
6. **资源限制**：为每个 Deployment 设置 `resources.requests` 和 `resources.limits`，防止资源争用。

---

## 相关文件

- [`../../helm/domino/`](../../helm/domino/) — Helm Chart 源码
- [`../../helm/README.md`](../../helm/README.md) — Helm 操作快速参考
- [`../docker/compose.yaml`](../docker/compose.yaml) — Docker Compose 部署
