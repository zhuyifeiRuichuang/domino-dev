import os
import tomli
import tomli_w
import yaml
import subprocess
import re
import shutil
import requests
import time
from concurrent.futures import ThreadPoolExecutor
import base64
from pathlib import Path
from rich.console import Console
from yaml.resolver import BaseResolver
from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as crypto_default_backend
from tempfile import NamedTemporaryFile, TemporaryDirectory
from kubernetes import client, config

from domino.cli.utils.constants import COLOR_PALETTE, DOMINO_HELM_PATH, DOMINO_HELM_VERSION, DOMINO_HELM_REPOSITORY


class AsLiteral(str):
    pass


def represent_literal(dumper, data):
    return dumper.represent_scalar(BaseResolver.DEFAULT_SCALAR_TAG, data, style="|")


yaml.add_representer(AsLiteral, represent_literal)


console = Console()


def create_ssh_pair_key() -> None:
    # Create SSH key pair for GitHub Workflows
    console.print("Generating SSH key pair for GitHub Workflows...")
    key = rsa.generate_private_key(
        backend=crypto_default_backend(),
        public_exponent=65537,
        key_size=4096
    )

    private_key = key.private_bytes(
        crypto_serialization.Encoding.PEM,
        crypto_serialization.PrivateFormat.PKCS8,
        crypto_serialization.NoEncryption()
    )
    public_key = key.public_key().public_bytes(
        crypto_serialization.Encoding.OpenSSH,
        crypto_serialization.PublicFormat.OpenSSH
    )
    return private_key, public_key


def prepare_platform(
    cluster_name: str,
    workflows_repository: str,
    github_workflows_ssh_private_key: str,
    github_default_pieces_repository_token: str,
    github_workflows_token: str,
) -> None:
    # Create local configuration file updated with user-provided arguments
    config_file_path = Path(__file__).resolve().parent / "config-domino-local.toml"
    with open(str(config_file_path), "rb") as f:
        config_dict = tomli.load(f)

    running_path = str(Path().cwd().resolve())
    config_dict["path"]["DOMINO_LOCAL_RUNNING_PATH"] = running_path
    config_dict["kind"]["DOMINO_KIND_CLUSTER_NAME"] = cluster_name

    config_dict['github']['DOMINO_GITHUB_WORKFLOWS_REPOSITORY'] = workflows_repository.split("github.com/")[-1].strip('/')

    if not github_workflows_ssh_private_key:
        private_key, public_key = create_ssh_pair_key()
        config_dict["github"]["DOMINO_GITHUB_WORKFLOWS_SSH_PRIVATE_KEY"] = base64.b64encode(private_key).decode('utf-8')
        config_dict["github"]["DOMINO_GITHUB_WORKFLOWS_SSH_PUBLIC_KEY"] = public_key.decode("utf-8")
    else:
        config_dict["github"]["DOMINO_GITHUB_WORKFLOWS_SSH_PRIVATE_KEY"] = github_workflows_ssh_private_key

    config_dict['github']['DOMINO_GITHUB_ACCESS_TOKEN_WORKFLOWS'] = github_workflows_token
    config_dict['github']['DOMINO_DEFAULT_PIECES_REPOSITORY_TOKEN'] = github_default_pieces_repository_token

    with open("config-domino-local.toml", "wb") as f:
        tomli_w.dump(config_dict, f)

    console.print("")
    console.print(f"Domino is prepared to run at: {running_path}")
    console.print(f"You can check and modify the configuration file at: {running_path}/config-domino-local.toml")
    console.print("Next, run: `domino platform create`")
    console.print("")


def create_platform(install_airflow: bool = True, use_gpu: bool = False) -> None:
    # Load configuration values
    with open("config-domino-local.toml", "rb") as f:
        platform_config = tomli.load(f)

    # Create kind config file and run bash script to create Kind cluster
    kubeadm_config_patches = dict(
        kind="InitConfiguration",
        nodeRegistration=dict(
            kubeletExtraArgs={
                "node-labels": "ingress-ready=true"
            }
        )
    )

    kubeadm_parsed = AsLiteral(yaml.dump(kubeadm_config_patches))
    use_gpu_dict = {} if not use_gpu else {"gpus": True}
    kind_config = dict(
        kind="Cluster",
        apiVersion="kind.x-k8s.io/v1alpha4",
        nodes=[
            dict(
                role="control-plane",
                kubeadmConfigPatches=[kubeadm_parsed],
                extraPortMappings=[
                    dict(
                        containerPort=80,
                        hostPort=80,
                        listenAddress="0.0.0.0",
                        protocol="TCP"
                    ),
                    dict(
                        containerPort=443,
                        hostPort=443,
                        listenAddress="0.0.0.0",
                        protocol="TCP"
                    )
                ]
            ),
            dict(
                role="worker",
                extraMounts=[
                    dict(
                        hostPath=platform_config["path"]["DOMINO_LOCAL_RUNNING_PATH"] + "/workflow_shared_storage",
                        containerPath="/cluster_shared_storage",
                        readOnly=False,
                        propagation="Bidirectional"
                    ),
                ],
                **use_gpu_dict
            ),
        ]
    )
    with open("kind-cluster-config.yaml", "w") as f:
        yaml.dump(kind_config, f)

    cluster_name = platform_config["kind"]["DOMINO_KIND_CLUSTER_NAME"]

    # Delete previous Kind cluster
    console.print("")
    console.print(f"Removing previous Kind cluster - {cluster_name}...")
    result = subprocess.run(["kind", "delete", "cluster", "--name", cluster_name], capture_output=True, text=True)
    if result.returncode != 0:
        error_message = result.stderr.strip() if result.stderr else result.stdout.strip()
        raise Exception(f"An error occurred while deleting previous Kind cluster - {cluster_name}: {error_message}")
    console.print("")

    # Create new Kind cluster
    console.print(f"Creating new Kind cluster - {cluster_name}...")
    result = subprocess.run(["kind", "create", "cluster", "--name", cluster_name, "--config", "kind-cluster-config.yaml"])
    if result.returncode != 0:
        error_message = result.stderr.strip() if result.stderr else result.stdout.strip()
        raise Exception(f"An error occurred while creating Kind cluster - {cluster_name}: {error_message}")
    console.print("")
    console.print("Kind cluster created successfully!", style=f"bold {COLOR_PALETTE.get('success')}")

    # Install Ingress NGINX controller
    console.print("")
    console.print("Installing NGINX controller...")
    subprocess.run(["kubectl", "apply", "-f", "https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml"], stdout=subprocess.DEVNULL)
    result = subprocess.run(["kubectl", "wait", "--namespace", "ingress-nginx", "--for", "condition=ready", "pod", "--selector=app.kubernetes.io/component=controller", "--timeout=660s"])
    if result.returncode != 0:
        error_message = result.stderr.strip() if result.stderr else result.stdout.strip()
        raise Exception("An error occurred while installing NGINX controller: {error_message}")
    console.print("NGINX controller installed successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
    console.print("")

    domino_airflow_image = "ghcr.io/tauffer-consulting/domino-airflow-base"
    domino_airflow_image_tag = 'latest'
    domino_frontend_image = "ghcr.io/tauffer-consulting/domino-frontend:k8s"
    domino_rest_image = "ghcr.io/tauffer-consulting/domino-rest:latest"

    # In order to use nvidia gpu in our cluster we need nvidia plugins to be installed.
    # We can use nvidia operator to install nvidia plugins.
    # References:
    #     https://catalog.ngc.nvidia.com/orgs/nvidia/containers/gpu-operator
    #     https://jacobtomlinson.dev/posts/2022/quick-hack-adding-gpu-support-to-kind/
    if use_gpu:
        console.print("Installing NVIDIA GPU Operator...")
        nvidia_gpu_operator_add_repo_command = [
            "helm", "repo", "add", "nvidia", "https://nvidia.github.io/gpu-operator",
        ]
        subprocess.run(nvidia_gpu_operator_add_repo_command)
        helm_update_command = ["helm", "repo", "update"]
        subprocess.run(helm_update_command)

        # We don't need driver as we are using kind and our host machine already has nvidia driver that is why we are disabling it.
        nvidia_plugis_install_command = "helm install --wait --generate-name -n gpu-operator --create-namespace nvidia/gpu-operator --set driver.enabled=false"
        subprocess.run(nvidia_plugis_install_command, shell=True)


    # Override values for Domino Helm chart
    db_enabled = platform_config['domino_db'].get("DOMINO_CREATE_DATABASE", True)
    token_pieces = platform_config["github"]["DOMINO_DEFAULT_PIECES_REPOSITORY_TOKEN"]
    token_workflows = platform_config["github"]["DOMINO_GITHUB_ACCESS_TOKEN_WORKFLOWS"]
    domino_values_override_config = {
        "github_access_token_pieces": token_pieces,
        "github_access_token_workflows": token_workflows,
        "frontend": {
            "enabled": True,
            "image": domino_frontend_image,
            "apiEnv": "prod",
            "deployMode": "k8s",
        },
        "rest": {
            "enabled": True,
            "image": domino_rest_image,
            "workflowsRepository": platform_config['github']['DOMINO_GITHUB_WORKFLOWS_REPOSITORY'],
            "createDefaultUser": platform_config['domino_db'].get('DOMINO_CREATE_DEFAULT_USER', True)
        },
        "database": {
            "enabled": db_enabled,
            "image": "postgres:13",
            "name": "postgres",
            "user": "postgres",
            "password": "postgres",
            "port": "5432",
        }
    }

    # Only add database values if database is enabled
    # If not enabled will use always the default values
    if not db_enabled:
        domino_values_override_config['database'] = {
            **domino_values_override_config['database'],
            "host": platform_config['domino_db']["DOMINO_DB_HOST"],
            "name":  platform_config['domino_db']["DOMINO_DB_NAME"],
            "user": platform_config['domino_db']["DOMINO_DB_USER"],
            "password": platform_config['domino_db']["DOMINO_DB_PASSWORD"],
            "port": str(platform_config['domino_db'].get("DOMINO_DB_PORT", 5432))
        }

    # Override values for Airflow Helm chart
    airflow_ssh_config = dict(
        gitSshKey=f"{platform_config['github']['DOMINO_GITHUB_WORKFLOWS_SSH_PRIVATE_KEY']}",
    )
    airflow_ssh_config_parsed = AsLiteral(yaml.dump(airflow_ssh_config))

    airflow_values_override_config = {
        "env": [
            {
                "name": "DOMINO_DEPLOY_MODE",
                "value": "k8s"
            },
        ],
        "images": {
            "useDefaultImageForMigration": False,
            "airflow": {
                "repository": domino_airflow_image,
                "tag": domino_airflow_image_tag,
                "pullPolicy": "IfNotPresent"
            }
        },
        "extraSecrets": {
            "airflow-ssh-secret": {
                "data": airflow_ssh_config_parsed
            }
        },
        "config": {
            "api": {
                "auth_backends": "airflow.api.auth.backend.basic_auth"
            },
        },
        "dags": {
            "gitSync": {
                "enabled": True,
                "wait": 60,
                "repo": f"ssh://git@github.com/{platform_config['github']['DOMINO_GITHUB_WORKFLOWS_REPOSITORY']}.git",
                "branch": "main",
                "subPath": "workflows",
                "sshKeySecret": "airflow-ssh-secret"
            },
        },
        "migrateDatabaseJob": {
            "jobAnnotations": {
                "sidecar.istio.io/inject": "false"
            },
            "annotations": {
                "sidecar.istio.io/inject": "false"
            },
        },
        "createUserJob": {
            "jobAnnotations": {
                "sidecar.istio.io/inject": "false"
            },
            "annotations": {
                "sidecar.istio.io/inject": "false"
            },
        },
    }

    # Update Helm repositories
    subprocess.run(["helm", "repo", "add", "domino", DOMINO_HELM_REPOSITORY])
    subprocess.run(["helm", "repo", "add", "apache-airflow", "https://airflow.apache.org/"])  # ref: https://github.com/helm/helm/issues/8036
    subprocess.run(["helm", "repo", "update"])

    # Install Airflow Helm Chart
    if install_airflow:
        console.print('Installing Apache Airflow...')
        # Create temporary file with airflow values
        with NamedTemporaryFile(suffix='.yaml', mode="w") as fp:
            yaml.dump(airflow_values_override_config, fp)
            commands = [
                "helm", "install",
                "-f", str(fp.name),
                "airflow",
                "apache-airflow/airflow",
                "--version", " 1.11.0",
            ]
            subprocess.run(commands)

    # Install Domino Helm Chart
    console.print('Installing Domino using remote helm...')
    with TemporaryDirectory() as tmp_dir:
        console.print("Downloading Domino Helm chart...")
        subprocess.run([
            "helm",
            "pull",
            DOMINO_HELM_PATH,
            "--untar",
            "-d",
            tmp_dir
        ])
        with NamedTemporaryFile(suffix='.yaml', mode="w") as fp:
            yaml.dump(domino_values_override_config, fp)
            console.print('Installing Domino...')
            commands = [
                "helm", "install",
                "-f", str(fp.name),
                "domino",
                f"{tmp_dir}/domino",
            ]
            subprocess.run(commands)

    console.print("")
    console.print("K8s resources created successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
    console.print("You can now access the Domino frontend at: http://localhost/")
    console.print("Domino's REST API: http://localhost/api/")
    console.print("Domino's REST API Swagger: http://localhost/api/docs")
    console.print("")


def destroy_platform() -> None:
    # Delete Kind cluster
    with open("config-domino-local.toml", "rb") as f:
        platform_config = tomli.load(f)
    cluster_name = platform_config["kind"]["DOMINO_KIND_CLUSTER_NAME"]
    console.print(f"Removing Kind cluster - {cluster_name}...")
    result = subprocess.run(["kind", "delete", "cluster", "--name", cluster_name], capture_output=True, text=True)
    if result.returncode != 0:
        error_message = result.stderr.strip() if result.stderr else result.stdout.strip()
        raise Exception(f"An error occurred while deleting Kind cluster - {cluster_name}: {error_message}")
    console.print("")
    console.print("Kind cluster removed successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
    console.print("")


def run_platform_compose(
    github_token: str,
    use_config_file: bool = False,
    debug: bool = False
) -> None:
    console.print("Starting Domino Platform using Docker Compose.")
    console.print("Please wait, this might take a few minutes...")
    # Database default settings
    create_database = True
    os.environ['DOMINO_CREATE_DEFAULT_USER'] = 'true'
    os.environ['DOMINO_DEFAULT_PIECES_REPOSITORY_TOKEN'] = github_token
    if use_config_file:
        console.print("Using config file...")
        with open("config-domino-local.toml", "rb") as f:
            platform_config = tomli.load(f)
        create_database = platform_config['domino_db'].get('DOMINO_CREATE_DATABASE', True)
        os.environ['DOMINO_CREATE_DEFAULT_USER'] = str(platform_config['domino_db'].get('DOMINO_CREATE_DEFAULT_USER', 'true')).lower()

        if not create_database:
            os.environ['DOMINO_DB_HOST'] = platform_config['domino_db'].get("DOMINO_DB_HOST", 'postgres')
            os.environ['DOMINO_DB_PORT'] = platform_config['domino_db'].get("DOMINO_DB_PORT", 5432)
            os.environ['DOMINO_DB_USER'] = platform_config['domino_db'].get("DOMINO_DB_USER", 'postgres')
            os.environ['DOMINO_DB_PASSWORD'] = platform_config['domino_db'].get("DOMINO_DB_PASSWORD", 'postgres')
            os.environ['DOMINO_DB_NAME'] = platform_config['domino_db'].get("DOMINO_DB_NAME", 'postgres')
            os.environ['NETWORK_MODE'] = 'bridge'

        # If running database in an external local container, set network mode to host
        if platform_config['domino_db'].get('DOMINO_DB_HOST') in ['localhost', '0.0.0.0', '127.0.0.1']:
            os.environ['NETWORK_MODE'] = 'host'

    # Create local directories
    local_path = Path(".").resolve()
    domino_dir = local_path / "domino_data"
    domino_dir.mkdir(parents=True, exist_ok=True)
    domino_dir.chmod(0o777)

    airflow_base = local_path / 'airflow'
    airflow_logs_dir = airflow_base / "logs"
    airflow_logs_dir.mkdir(parents=True, exist_ok=True)
    airflow_dags_dir = airflow_base / "dags"
    airflow_dags_dir.mkdir(parents=True, exist_ok=True)
    airflow_plugins_dir = airflow_base / "plugins"
    airflow_plugins_dir.mkdir(parents=True, exist_ok=True)
    airflow_base.chmod(0o777)

    # Copy docker-compose.yaml file from deploy/docker to local path
    if create_database:
        docker_compose_path = Path(__file__).resolve().parent.parent.parent / "deploy" / "docker" / "compose.yaml"
    else:
        # For production with external database
        docker_compose_path = Path(__file__).resolve().parent / "docker-compose-without-database.yaml"
    shutil.copy(str(docker_compose_path), "./docker-compose.yaml")

    # Environment variables
    environment = os.environ.copy()
    environment['DOMINO_DEPLOY_MODE'] = 'docker-compose'

    # Run docker compose pull (only for pre-built images, not auto-build)
    console.print("\nPulling Docker images...")
    pull_cmd = [
        "docker",
        "compose",
        "pull"
    ]
    pull_process = subprocess.Popen(pull_cmd, env=environment)
    pull_process.wait()
    if pull_process.returncode == 0:
        console.print(" \u2713 Docker images pulled successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
    else:
        console.print("Docker images pull failed. Will attempt build...", style=f"bold {COLOR_PALETTE.get('warning')}")

    # Run docker compose up (will build if images not found)
    console.print("\nStarting services...")
    cmd = [
        "docker",
        "compose",
        "up",
        "--build"  # Auto-build images if not found
    ]

    if debug:
        subprocess.Popen(cmd, env=environment)
    else:
        airflow_redis_ready = False
        airflow_database_ready = False
        airflow_init_ready = False
        airflow_triggerer_ready = False
        airflow_worker_ready = False
        airflow_webserver_ready = False
        airflow_scheduler_ready = False
        domino_database_ready = False

        process = subprocess.Popen(cmd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Read and filter the output
        def customize_message(
            line: str,
            airflow_redis_ready: bool = False,
            airflow_database_ready: bool = False,
            airflow_init_ready: bool = False,
            airflow_triggerer_ready: bool = False,
            airflow_worker_ready: bool = False,
            airflow_webserver_ready: bool = False,
            airflow_scheduler_ready: bool = False,
            domino_database_ready: bool = False,
        ):
            line = line.lower()
            line = re.sub(r'\s+', ' ', line)
            if not airflow_redis_ready and "airflow-redis" in line and "ready to accept connections tcp" in line:
                console.print(" \u2713 Airflow Redis service started successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                airflow_redis_ready = True
            if not airflow_database_ready and "airflow-postgres" in line and ("ready" in line or "skipping" in line):
                console.print(" \u2713 Airflow database service started successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                airflow_database_ready = True
            if not airflow_init_ready and "airflow-init" in line and "exited with code 0" in line:
                console.print(" \u2713 Airflow pre-initialization service completed successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                airflow_init_ready = True
            if not airflow_triggerer_ready and "airflow-triggerer" in line and "starting" in line:
                console.print(" \u2713 Airflow triggerer service started successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                airflow_triggerer_ready = True
            if not airflow_worker_ready and "airflow-domino-worker" in line and "execute_command" in line:
                console.print(" \u2713 Airflow worker service started successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                airflow_worker_ready = True
            if not airflow_webserver_ready and "airflow-webserver" in line and "health" in line and "200" in line:
                console.print(" \u2713 Airflow webserver service started successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                airflow_webserver_ready = True
            if not airflow_scheduler_ready and "airflow-domino-scheduler" in line and "launched" in line:
                console.print(" \u2713 Airflow scheduler service started successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                airflow_scheduler_ready = True
            if not domino_database_ready and "domino-postgres" in line and ("ready" in line or "skipping" in line):
                console.print(" \u2713 Domino database service started successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                domino_database_ready = True
            return airflow_redis_ready, airflow_database_ready, airflow_init_ready, airflow_triggerer_ready, airflow_worker_ready, airflow_webserver_ready, airflow_scheduler_ready, domino_database_ready

        def check_domino_processes():
            while True:
                try:
                    frontend_response = requests.get("http://localhost:3000").status_code
                    rest_response = requests.get("http://localhost:8000/health-check").status_code
                    if frontend_response == 200 and rest_response == 200:
                        console.print(" \u2713 Domino REST service started successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                        console.print(" \u2713 Domino frontend service started successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                        break
                except requests.exceptions.RequestException:
                    pass
                time.sleep(5)

        for line in process.stdout:
            airflow_redis_ready, airflow_database_ready, airflow_init_ready, airflow_triggerer_ready, airflow_worker_ready, airflow_webserver_ready, airflow_scheduler_ready, domino_database_ready = customize_message(
                line, airflow_redis_ready, airflow_database_ready, airflow_init_ready, airflow_triggerer_ready,
                airflow_worker_ready, airflow_webserver_ready, airflow_scheduler_ready, domino_database_ready)
            if all([
                airflow_redis_ready,
                airflow_database_ready,
                airflow_init_ready,
                airflow_triggerer_ready,
                airflow_worker_ready,
                airflow_webserver_ready,
                airflow_scheduler_ready,
                domino_database_ready,
            ]):
                check_domino_processes()
                console.print("\n \u2713 All services for Domino Platform started successfully!", style=f"bold {COLOR_PALETTE.get('success')}")
                console.print("")
                console.print("You can now access them at")
                console.print("Domino UI: http://localhost:3000")
                console.print("Domino REST API: http://localhost:8000")
                console.print("Domino REST API Docs: http://localhost:8000/docs")
                console.print("Airflow webserver: http://localhost:8080")
                console.print("")
                console.print("To stop the platform, run:")
                console.print("    $ domino platform stop-compose")
                console.print("")
                break


def stop_platform_compose() -> None:
    # If "docker-compose.yaml" file is present in current working path, try run "docker compose down"
    docker_compose_path = Path.cwd().resolve() / "docker-compose.yaml"
    if docker_compose_path.exists():
        # Setting this environment variable to empty string just to print cleaner messages to terminal
        environment = os.environ.copy()
        environment['DOMINO_DEFAULT_PIECES_REPOSITORY_TOKEN'] = ''
        environment['AIRFLOW_UID'] = ''
        cmd = [
            "docker",
            "compose",
            "down"
        ]
        completed_process = subprocess.run(cmd, env=environment)
        if completed_process.returncode == 0:
            console.print("\n \u2713 Domino Platform stopped successfully. All containers were removed.\n", style=f"bold {COLOR_PALETTE.get('success')}")
        return

    # Stop and remove containers by name (fallback method)
    def stop_and_remove_container(container_name):
        print(f"Stopping {container_name}...")
        process = subprocess.Popen(f"docker stop {container_name}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            pass
        else:
            print(stdout.decode())

        print(f"Removing {container_name}...")
        process = subprocess.Popen(f"docker rm {container_name}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            pass
        else:
            print(stdout.decode())

    try:
        container_names = [
            "domino-frontend",
            "domino-rest",
            "domino-postgres",
            "domino-docker-proxy",
            "airflow-scheduler",
            "airflow-worker",
            "airflow-webserver",
            "airflow-triggerer",
            "domino-redis",
            "airflow-postgres",
            "airflow-flower",
            "airflow-cli",
            "airflow-init",
        ]
        with ThreadPoolExecutor() as executor:
            executor.map(stop_and_remove_container, container_names)
        console.print("\n \u2713 Domino Platform stopped successfully. All containers were removed.\n", style=f"bold {COLOR_PALETTE.get('success')}")
    except Exception as e:
        print(f"An error occurred: {e}")
