from pydantic import BaseModel
from typing import List, Optional
from database.models.enums import Permission, RepositorySource, UserWorkspaceStatus
from schemas.responses.base import PaginationSet


class CreateWorkspaceResponse(BaseModel):
    id: int
    name: str
    user_permission: Permission


class WorkspaceBase(BaseModel):
    workspace_id: int
    workspace_name: str
    user_permission: Permission


class WorkspaceWorkflows(BaseModel):
    workflow_id: int


class WorkspaceRepositories(BaseModel):
    repository_id: int
    repository_source: RepositorySource
    repository_name: str


class WorkspaceUsers(BaseModel):
    user_id: int
    permission: Permission


class AssignWorkspaceResponse(BaseModel):
    user_id: int
    workspaces: List[WorkspaceBase]


class ListUserWorkspacesResponse(BaseModel):
    id: int
    workspace_name: str
    user_permission: Permission
    status: UserWorkspaceStatus
    git_access_token_filled: bool
    # Legacy field for backward compatibility
    github_access_token_filled: bool = False

    def __init__(self, **data):
        # Keep both fields in sync
        if 'git_access_token_filled' in data and 'github_access_token_filled' not in data:
            data['github_access_token_filled'] = data['git_access_token_filled']
        elif 'github_access_token_filled' in data and 'git_access_token_filled' not in data:
            data['git_access_token_filled'] = data['github_access_token_filled']
        super().__init__(**data)


class ListWorkspaceUsersResponseData(BaseModel):
    user_id: int
    user_email: str
    user_permission: Permission
    status: UserWorkspaceStatus


class ListWorkspaceUsersResponse(BaseModel):
    data: List[ListWorkspaceUsersResponseData]
    metadata: PaginationSet


class GetWorkspaceResponse(BaseModel):
    id: int
    workspace_name: str
    user_permission: str
    status: UserWorkspaceStatus
    git_access_token_filled: bool
    git_platform_type: Optional[str] = None
    git_platform_url: Optional[str] = None
    # Legacy field
    github_access_token_filled: bool = False

    def __init__(self, **data):
        if 'git_access_token_filled' in data and 'github_access_token_filled' not in data:
            data['github_access_token_filled'] = data['git_access_token_filled']
        elif 'github_access_token_filled' in data and 'git_access_token_filled' not in data:
            data['git_access_token_filled'] = data['github_access_token_filled']
        super().__init__(**data)


class PatchWorkspaceResponse(GetWorkspaceResponse):
    ...
