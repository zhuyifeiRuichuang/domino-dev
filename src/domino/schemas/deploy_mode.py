from enum import Enum


# Enum type for deploy_mode
class DeployModeType(str, Enum):
    """Domino 部署模式类型

    简化为三种标准部署模式：
    - host: 主机环境部署（直接在宿主机运行 Piece）
    - docker-compose: Docker Compose 部署（单机/本地生产环境）
    - k8s: Kubernetes 部署（集群生产环境）
    """
    host = "host"
    docker_compose = "docker-compose"
    k8s = "k8s"


# 向后兼容的别名
LocalDeployMode = DeployModeType
