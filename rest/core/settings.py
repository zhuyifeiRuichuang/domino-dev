from pydantic_settings import BaseSettings
from typing import Union, Optional
import os
from database.models.enums import RepositorySource


class Settings(BaseSettings):
    # General app config
    VERSION: str = "0.1.0"
    APP_TITLE: str = "Domino REST api"

    # Database config
    DB_URL: str = 'postgresql://{user}:{password}@{host}:{port}/{name}'.format(
        user=os.environ.get("DOMINO_DB_USER", "postgres"),
        password=os.environ.get("DOMINO_DB_PASSWORD", "postgres"),
        host=os.environ.get("DOMINO_DB_HOST", "localhost"),
        port=os.environ.get("DOMINO_DB_PORT", "5432"),
        name=os.environ.get("DOMINO_DB_NAME", "postgres"),
    )

    # Auth config
    AUTH_SECRET_KEY: str = os.environ.get('AUTH_SECRET_KEY', "CHANGE_ME_IN_PRODUCTION_USE_RANDOM_256BIT_KEY")
    AUTH_ALGORITHM: str = os.environ.get('AUTH_ALGORITHM', "HS256")
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get('AUTH_ACCESS_TOKEN_EXPIRE_MINUTES', '600'))
    ADMIN_USER_EMAIL: str = os.environ.get('ADMIN_USER_EMAIL', "admin@email.com")
    ADMIN_USER_PASSWORD: str = os.environ.get('ADMIN_USER_PASSWORD', "admin")
    CREATE_DEFAULT_USER: bool = os.environ.get('CREATE_DEFAULT_USER', 'true').lower() in ('true', '1', 'yes')

    # Secrets encryption config
    # Must be a URL-safe base64-encoded 32-byte key. Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    SECRETS_SECRET_KEY: str = os.environ.get('SECRETS_SECRET_KEY', 'j1DsRJ-ehxU_3PbXW0c_-U4nTOx3knRB4zzWguMVaio=')
    # Used to encrypt the git platform access token stored in the workspace
    GIT_TOKEN_SECRET_KEY: str = os.environ.get(
        'GIT_TOKEN_SECRET_KEY',
        os.environ.get('GITHUB_TOKEN_SECRET_KEY', 'j1DsRJ-ehxU_3PbXW0c_-U4nTOx3knRB4zzWguMVaio=')
    )

    # -----------------------------------------------------------------------
    # Workflow storage mode
    # DOMINO_WORKFLOW_STORAGE_MODE: 'local' (default for docker compose) or 'git'
    #   - local: DAGs are written directly to the local filesystem (shared with Airflow)
    #   - git:   DAGs are pushed to a remote Git repository
    # -----------------------------------------------------------------------
    DOMINO_WORKFLOW_STORAGE_MODE: str = os.environ.get('DOMINO_WORKFLOW_STORAGE_MODE', 'local')

    # Local DAG path (used when DOMINO_WORKFLOW_STORAGE_MODE == 'local')
    DOMINO_LOCAL_WORKFLOWS_REPOSITORY: str = os.environ.get('DOMINO_LOCAL_WORKFLOWS_REPOSITORY', '/opt/airflow/dags')

    # Remote Git repository for DAG storage (used when DOMINO_WORKFLOW_STORAGE_MODE == 'git')
    DOMINO_WORKFLOWS_GIT_REPO_URL: str = os.environ.get('DOMINO_WORKFLOWS_GIT_REPO_URL', '')
    DOMINO_WORKFLOWS_GIT_REPO_BRANCH: str = os.environ.get('DOMINO_WORKFLOWS_GIT_REPO_BRANCH', 'main')
    DOMINO_WORKFLOWS_GIT_TOKEN: Optional[str] = os.environ.get('DOMINO_WORKFLOWS_GIT_TOKEN', None)
    # SSH private key path (alternative to token)
    DOMINO_WORKFLOWS_GIT_SSH_KEY_PATH: Optional[str] = os.environ.get('DOMINO_WORKFLOWS_GIT_SSH_KEY_PATH', None)

    # Legacy GitHub-specific settings (kept for backward compatibility)
    DOMINO_GITHUB_ACCESS_TOKEN_WORKFLOWS: Optional[str] = os.environ.get('DOMINO_GITHUB_ACCESS_TOKEN_WORKFLOWS', None)
    DOMINO_GITHUB_WORKFLOWS_REPOSITORY: str = os.environ.get('DOMINO_GITHUB_WORKFLOWS_REPOSITORY', '')

    # Default piece repository token (optional - only needed for private repos)
    DOMINO_DEFAULT_PIECES_REPOSITORY_TOKEN: Optional[str] = os.environ.get('DOMINO_DEFAULT_PIECES_REPOSITORY_TOKEN', None)
    DEFAULT_REPOSITORIES_LIST: list = [
        dict(
            path="Tauffer-Consulting/default_domino_pieces",
            version='0.8.1',
            source='github',
            require_token=False,
            url='https://github.com/Tauffer-Consulting/default_domino_pieces'
        ),
        dict(
            path="Tauffer-Consulting/openai_domino_pieces",
            version='0.7.2',
            source='github',
            require_token=True,
            url='https://github.com/Tauffer-Consulting/openai_domino_pieces'
        ),
        dict(
            path="Tauffer-Consulting/social_media_domino_pieces",
            version='0.5.4',
            source='github',
            require_token=True,
            url='https://github.com/Tauffer-Consulting/social_media_domino_pieces'
        ),
        dict(
            path="Tauffer-Consulting/data_apis_domino_pieces",
            version='0.2.3',
            source='github',
            require_token=True,
            url='https://github.com/Tauffer-Consulting/data_apis_domino_pieces'
        ),
        dict(
            path="Tauffer-Consulting/ml_domino_pieces",
            version='0.2.2',
            source='github',
            require_token=True,
            url='https://github.com/Tauffer-Consulting/ml_domino_pieces'
        )
    ]

    # -----------------------------------------------------------------------
    # Airflow config
    # AIRFLOW_WEBSERVER_HOST: full URL, e.g. http://airflow-webserver:8080 or http://192.168.1.10:8080
    # -----------------------------------------------------------------------
    AIRFLOW_ADMIN_CREDENTIALS: dict = {
        "username": os.environ.get('AIRFLOW_ADMIN_USERNAME', "admin"),
        "password": os.environ.get('AIRFLOW_ADMIN_PASSWORD', "admin")
    }
    # Accept both with and without trailing slash; client normalises it
    AIRFLOW_WEBSERVER_HOST: str = os.environ.get(
        'AIRFLOW_WEBSERVER_HOST',
        os.environ.get('AIRFLOW_WEBSERVER_URL', 'http://airflow-webserver:8080')
    ).rstrip('/')

    # Default repositories
    DEFAULT_STORAGE_REPOSITORY: dict = dict(
        name="default_storage_repository",
        path="default_storage_repository",
        source=getattr(RepositorySource, 'default').value,
        version="0.0.1",
        url="domino-default/default_storage_repository"
    )

    DEPLOY_MODE: str = os.environ.get('DOMINO_DEPLOY_MODE', 'local-k8s')

    CONDITIONAL_ENDPOINTS_ENABLED: bool = False if DEPLOY_MODE == 'local-compose' else True


class LocalK8sSettings(Settings):
    SERVER_HOST: str = "0.0.0.0"
    DEBUG: bool = True
    PORT: int = 8000
    RELOAD: bool = True
    CORS: dict = {
        "origins": [
            "*",
        ],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    ROOT_PATH: str = '/api'


class LocalComposeSettings(Settings):
    SERVER_HOST: str = "0.0.0.0"
    DEBUG: bool = True
    PORT: int = 8000
    RELOAD: bool = True
    CORS: dict = {
        "origins": [
            "*",
        ],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }

    ROOT_PATH: str = '/'


class ProdSettings(Settings):
    SERVER_HOST: str = "0.0.0.0"
    DEBUG: bool = False
    PORT: int = 8000
    RELOAD: bool = False
    CORS: dict = {
        "origins": [
            "*",
        ],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }

    # ROOT_PATH is based in proxy config. Must be the same as the path to the api in the proxy
    ROOT_PATH: str = '/api'


def get_settings():
    env = os.getenv("DOMINO_DEPLOY_MODE", "local-k8s-dev")
    settings_type = {
        "local-k8s": LocalK8sSettings(),
        "local-k8s-dev": LocalK8sSettings(),
        "local-compose": LocalComposeSettings(),
        "prod": ProdSettings(),
    }
    return settings_type.get(env, LocalK8sSettings())


settings: Settings = get_settings()
