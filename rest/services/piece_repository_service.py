from typing import List
import json
import tomli
from math import ceil
from datetime import datetime
from core.logger import get_configured_logger
from schemas.context.auth_context import AuthorizationContextData
from schemas.requests.piece_repository import CreateRepositoryRequest, PatchRepositoryRequest, ListRepositoryFilters
from schemas.responses.piece_repository import (
    CreateRepositoryReponse,
    GetRepositoryReleasesResponse,
    PatchRepositoryResponse,
    GetWorkspaceRepositoriesData,
    GetWorkspaceRepositoriesResponse,
    GetRepositoryReleaseDataResponse,
    GetRepositoryResponse
)
from schemas.responses.base import PaginationSet
from schemas.exceptions.base import ConflictException, ResourceNotFoundException, ForbiddenException, UnauthorizedException
from services.piece_service import PieceService
from services.secret_service import SecretService
from repository.workspace_repository import WorkspaceRepository
from repository.piece_repository_repository import PieceRepositoryRepository
from repository.workflow_repository import WorkflowRepository
from repository.secret_repository import SecretRepository
from database.models.enums import RepositorySource
from database.models import PieceRepository
from clients.github_rest_client import GithubRestClient
from clients.git_client import GitPlatformClient
from core.settings import settings


class PieceRepositoryService(object):
    def __init__(self) -> None:
        self.logger = get_configured_logger(self.__class__.__name__)
        self.piece_service = PieceService()
        self.secret_service = SecretService()
        self.workspace_repository = WorkspaceRepository()
        self.piece_repository_repository = PieceRepositoryRepository()
        self.workflow_repository = WorkflowRepository()
        self.secret_repository = SecretRepository()

        # TODO change token from app level to workspace level

    def get_piece_repository(self, piece_repository_id: int) -> GetRepositoryResponse:
        piece_repository = self.piece_repository_repository.find_by_id(piece_repository_id)
        if not piece_repository:
            raise ResourceNotFoundException()

        if not piece_repository.label:
            piece_repository.label = piece_repository.name

        response = GetRepositoryResponse(
            **piece_repository.to_dict(),
        )
        return response

    def get_pieces_repositories(
        self,
        workspace_id: int,
        page: int,
        page_size: int,
        filters: ListRepositoryFilters
    ) -> GetWorkspaceRepositoriesResponse:
        self.logger.info(f"Getting repositories for workspace {workspace_id}")
        pieces_repositories = self.piece_repository_repository.find_by_workspace_id(
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            filters=filters.model_dump(exclude_none=True)
        )
        data = []
        for piece_repository in pieces_repositories:
            if not piece_repository[0].label:
                piece_repository[0].label = piece_repository[0].name
            data.append(GetWorkspaceRepositoriesData(**piece_repository[0].to_dict()))

        count = 0 if not pieces_repositories else pieces_repositories[0].count
        metadata = PaginationSet(
            page=page,
            records=len(data),
            total=count,
            last_page=max(0, ceil(count / page_size) - 1)
        )
        response = GetWorkspaceRepositoriesResponse(data=data, metadata=metadata)
        return response

    def get_piece_repository_releases(self, source: str, path: str, auth_context: AuthorizationContextData) -> List[GetRepositoryReleasesResponse]:
        self.logger.info(f"Getting releases for repository {path}")

        token = auth_context.workspace.git_access_token if hasattr(auth_context.workspace, 'git_access_token') else None
        if not token:
            token = getattr(auth_context.workspace, 'github_access_token', None)
        if not token:
            token = settings.DOMINO_DEFAULT_PIECES_REPOSITORY_TOKEN
        if token and not token.strip():
            token = None

        git_client = self._build_git_client(source=source, path=path, token=token)

        if source == getattr(RepositorySource, 'github').value:
            tags = git_client.get_tags(path)
        elif source in (
            getattr(RepositorySource, 'gitlab').value,
            getattr(RepositorySource, 'gitea').value,
            getattr(RepositorySource, 'bitbucket').value,
        ):
            tags = git_client.get_tags(path)
        else:
            return []

        if not tags:
            return []
        return [GetRepositoryReleasesResponse(version=tag["name"], last_modified=tag.get("last_modified")) for tag in tags]

    def get_piece_repository_release_data(self, version: str, source:str, path: str, auth_context: AuthorizationContextData) -> GetRepositoryReleaseDataResponse:
        self.logger.info(f'Getting release data for repository {path}')

        token = getattr(auth_context.workspace, 'git_access_token', None) or \
                getattr(auth_context.workspace, 'github_access_token', None)
        if token is not None and not token.strip():
            token = None
        if not token:
            token = settings.DOMINO_DEFAULT_PIECES_REPOSITORY_TOKEN

        tag_data = self._read_repository_data(path=path, source=source, version=version, access_token=token)
        name = tag_data.get('config_toml').get('repository').get("REPOSITORY_NAME")
        description = tag_data.get('config_toml').get('repository').get("DESCRIPTION")
        pieces_list = list(tag_data.get('compiled_metadata').keys())
        response = GetRepositoryReleaseDataResponse(
            name=name,
            description=description,
            pieces=pieces_list
        )
        return response

    def patch_piece_repository(
        self,
        repository_id: int,
        piece_repository_data: PatchRepositoryRequest
    ) -> PatchRepositoryResponse:

        repository = self.piece_repository_repository.find_by_id(id=repository_id)
        if not repository:
            raise ResourceNotFoundException()
        self.logger.info(f"Updating piece repository {repository.id} for workspace {repository.workspace_id}")

        repository_files_metadata = self._read_repository_data(
            source=repository.source,
            path=repository.path,
            version=piece_repository_data.version
        )

        new_repo = PieceRepository(
            created_at=datetime.utcnow(),
            name=repository_files_metadata['config_toml'].get('repository').get('REPOSITORY_NAME'),
            source=repository.source,
            path=repository.path,
            version=piece_repository_data.version,
            dependencies_map=repository_files_metadata['dependencies_map'],
            compiled_metadata=repository_files_metadata['compiled_metadata'],
            workspace_id=repository.workspace_id
        )
        repository = self.piece_repository_repository.update(piece_repository=new_repo, id=repository.id)
        self._update_repository_pieces(
            source=repository.source,
            path=repository.path,
            repository_id=repository.id,
            version=piece_repository_data.version
        )

        # Check secrets to update
        all_current_secrets = set()
        for value in repository_files_metadata['dependencies_map'].values():
            for secret in value.get('secrets'):
                all_current_secrets.add(secret)

        for secret in all_current_secrets:
            db_secret = self.secret_repository.find_by_name_and_piece_repository_id(
                name=secret,
                piece_repository_id=repository.id
            )
            # If secret exists, don't touch it
            if db_secret:
                continue
            self.secret_service.create_workspace_repository_secret(
                workspace_id=repository.workspace_id,
                repository_id=repository.id,
                secret_name=secret,
            )
        # Delete secrets that are not in the version dependencies map
        self.secret_repository.delete_by_piece_repository_id_and_not_names(
            names=all_current_secrets,
            piece_repository_id=repository.id
        )

        return PatchRepositoryResponse(**repository.to_dict())

    def create_default_storage_repository(self, workspace_id: int):
        """
        Create default storage repository for workspace.
        Creating a repository will create all pieces and secrets to this repository.
        """
        self.logger.info(f"Creating default storage repository")

        new_repo = PieceRepository(
            name=settings.DEFAULT_STORAGE_REPOSITORY['name'],
            created_at=datetime.utcnow(),
            workspace_id=workspace_id,
            path=settings.DEFAULT_STORAGE_REPOSITORY['path'],
            source=settings.DEFAULT_STORAGE_REPOSITORY['source'],
            version=settings.DEFAULT_STORAGE_REPOSITORY['version'],
            url=settings.DEFAULT_STORAGE_REPOSITORY['url']
        )

        default_storage_repository = self.piece_repository_repository.create(piece_repository=new_repo)
        pieces = self.piece_service.create_default_storage_pieces(
            piece_repository_id=default_storage_repository.id,
        )
        self.secret_service.create_default_storage_pieces_secrets(
            pieces=pieces,
            workspace_id=workspace_id,
            repository_id=default_storage_repository.id
        )
        return default_storage_repository

    def create_piece_repository(
        self,
        piece_repository_data: CreateRepositoryRequest,
        auth_context: AuthorizationContextData
    ) -> CreateRepositoryReponse:

        self.logger.info(f"Creating piece repository for workspace {piece_repository_data.workspace_id}")
        repository = self.piece_repository_repository.find_by_path_and_workspace_id(
            path=piece_repository_data.path,
            workspace_id=piece_repository_data.workspace_id
        )
        if repository:
            raise ConflictException(message=f"Repository {piece_repository_data.path} already exists for this workspace")

        token = getattr(auth_context.workspace, 'git_access_token', None) or \
                getattr(auth_context.workspace, 'github_access_token', None)
        if token is not None and not token.strip():
            token = None
        if not token:
            token = settings.DOMINO_DEFAULT_PIECES_REPOSITORY_TOKEN
        repository_files_metadata = self._read_repository_data(
            source=piece_repository_data.source,
            path=piece_repository_data.path,
            version=piece_repository_data.version,
            access_token=token
        )
        new_repo = PieceRepository(
            created_at=datetime.utcnow(),
            name=repository_files_metadata['config_toml'].get('repository').get('REPOSITORY_NAME'),
            source=piece_repository_data.source,
            path=piece_repository_data.path,
            label=repository_files_metadata['config_toml'].get('repository').get('REPOSITORY_LABEL'),
            version=piece_repository_data.version,
            dependencies_map=repository_files_metadata['dependencies_map'],
            compiled_metadata=repository_files_metadata['compiled_metadata'],
            workspace_id=piece_repository_data.workspace_id,
            url=piece_repository_data.url
        )
        repository = self.piece_repository_repository.create(piece_repository=new_repo)
        try:
            # Create pieces for this repository in database
            self._update_repository_pieces(
                repository_id=repository.id,
                source=piece_repository_data.source,
                compiled_metadata=repository_files_metadata['compiled_metadata'],
                dependencies_map=repository_files_metadata['dependencies_map'],
            )
            # Create secrets for the repository with null values
            secrets_to_update = list()
            for value in repository_files_metadata['dependencies_map'].values():
                for secret in value.get('secrets'):
                    secrets_to_update.append(secret)
            secrets_to_update = list(set(secrets_to_update))

            for secret in secrets_to_update:
                self.secret_service.create_workspace_repository_secret(
                    workspace_id=piece_repository_data.workspace_id,
                    repository_id=repository.id,
                    secret_name=secret,
                )

            response = CreateRepositoryReponse(**repository.to_dict())
            return response
        except (BaseException, ForbiddenException, UnauthorizedException, ResourceNotFoundException) as e:
            self.logger.exception(e)
            self.piece_repository_repository.delete(id=repository.id)
            raise e

    def _build_git_client(self, source: str, path: str, token: str = None, url: str = None) -> GitPlatformClient:
        """
        Build a GitPlatformClient for the given source type and optional URL.

        Parameters
        ----------
        source : str
            One of 'github', 'gitlab', 'gitea', 'bitbucket', 'local'.
        path : str
            Repository path (owner/repo).
        token : str, optional
            Access token.
        url : str, optional
            Full repository URL. If provided, the base URL is extracted from it.
            This allows pointing to self-hosted instances.
        """
        platform_url_map = {
            "github": "https://github.com",
            "gitlab": "https://gitlab.com",
            "bitbucket": "https://bitbucket.org",
            # gitea has no canonical public instance
        }

        if url:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
        elif source in platform_url_map:
            base_url = platform_url_map[source]
        else:
            # Default to gitea with no specific URL
            base_url = "http://localhost:3000"

        return GitPlatformClient(
            platform_url=base_url,
            token=token,
            platform_type=source if source != "local" else "gitea",
        )

    def _read_data_from_git(self, path: str, version: str, source: str = "github", access_token: str = None, url: str = None) -> dict:
        """Read files from a specific version of repository using the generic git client.

        Args:
            path (str): Repository path (owner/repo)
            version (str): Tag version name
            source (str): Platform type (github, gitlab, gitea, bitbucket)
            access_token (str, optional): Authentication token
            url (str, optional): Full repository URL for self-hosted instances

        Raises:
            ResourceNotFoundException: If tag version is not found raise exception

        Returns:
            dict: dictionary containing repository data
        """
        git_client = self._build_git_client(source=source, path=path, token=access_token, url=url)
        tag = git_client.get_tag(repo_path=path, tag_name=version)
        if not tag:
            raise ResourceNotFoundException(message=f"Version {version} not found in repository {path}")

        commit_sha_ref = tag["commit_sha"]

        dependencies_map_bytes = git_client.get_file_content(
            repo_path=path,
            file_path='.domino/dependencies_map.json',
            ref=commit_sha_ref
        )
        dependencies_map = json.loads(dependencies_map_bytes.decode('utf-8'))

        compiled_metadata_bytes = git_client.get_file_content(
            repo_path=path,
            file_path='.domino/compiled_metadata.json',
            ref=commit_sha_ref
        )
        compiled_metadata = json.loads(compiled_metadata_bytes.decode('utf-8'))

        config_toml_bytes = git_client.get_file_content(
            repo_path=path,
            file_path='config.toml',
            ref=commit_sha_ref
        )
        config_toml = tomli.loads(config_toml_bytes.decode('utf-8'))

        return {
            "dependencies_map": dependencies_map,
            "compiled_metadata": compiled_metadata,
            "config_toml": config_toml,
        }

    # Keep legacy method name for backward compatibility
    def _read_data_from_github(self, path: str, version: str, github_access_token: str = None) -> dict:
        return self._read_data_from_git(path=path, version=version, source="github", access_token=github_access_token)

    def _update_repository_pieces(
        self,
        source: str,
        compiled_metadata: dict,
        dependencies_map: dict,
        repository_id: int,
    ):
        read_pieces_map = {
            "github": self.piece_service.check_pieces_to_update_github,
            "gitlab": self.piece_service.check_pieces_to_update_github,
            "gitea": self.piece_service.check_pieces_to_update_github,
            "bitbucket": self.piece_service.check_pieces_to_update_github,
        }
        handler = read_pieces_map.get(source, self.piece_service.check_pieces_to_update_github)
        handler(
            repository_id=repository_id,
            compiled_metadata=compiled_metadata,
            dependencies_map=dependencies_map,
        )

    def _read_repository_data(self, source: str, path: str, version: str, access_token: str = None, url: str = None, github_access_token: str = None):
        """Read repository metadata. Supports all configured git platforms."""
        # Accept legacy kwarg name
        token = access_token or github_access_token
        if source == "local":
            raise ResourceNotFoundException("Local source does not support remote reads.")
        return self._read_data_from_git(path=path, version=version, source=source, access_token=token, url=url)

    def delete_repository(self, piece_repository_id: int):
        repository = self.piece_repository_repository.find_by_id(id=piece_repository_id)
        if not repository:
            raise ResourceNotFoundException()

        if getattr(repository, 'source') == RepositorySource.default.value:
            raise ForbiddenException(message="Default repository can not be deleted.")

        results = self.workflow_repository.count_piece_repository_dependent_workflows(piece_repository_id=repository.id)
        if results > 0:
            raise ConflictException(message=f"Repository {repository.name} is used in {results} workflow{'' if results == 1 else 's'}, delete {'it' if results == 1 else 'them'} first.")

        self.piece_repository_repository.delete(id=piece_repository_id)