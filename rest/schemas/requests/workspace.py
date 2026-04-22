from pydantic import BaseModel, Field
from typing import Optional
from database.models.enums import MembersPermissions


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., description="Name of the workspace")


class PatchWorkspaceRequest(BaseModel):
    # Generic Git platform settings
    git_access_token: Optional[str] = Field(
        description='Access token for the Git platform (GitHub PAT, GitLab token, Gitea token, etc.)',
        default=None
    )
    git_platform_url: Optional[str] = Field(
        description='Base URL of the Git platform, e.g. https://github.com, https://gitlab.mycompany.com, http://gitea.local:3000',
        default=None
    )
    git_platform_type: Optional[str] = Field(
        description='Platform type: github | gitlab | gitea | bitbucket',
        default=None
    )
    git_username: Optional[str] = Field(
        description='Username for HTTP Basic auth (used with some platforms like Gitea)',
        default=None
    )

    # Legacy field – still accepted for backward compatibility
    github_access_token: Optional[str] = Field(
        description='[Deprecated] Use git_access_token instead.',
        default=None
    )


class AssignWorkspaceRequest(BaseModel):
    permission: MembersPermissions
    user_email: str = Field(..., description="Email of the user to be assigned to the workspace")
