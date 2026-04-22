from pydantic import BaseModel, Field
from typing import Optional
from database.models.enums import RepositorySource
import enum


class RepositorySourceRequestEnum(str, enum.Enum):
    github = 'github'
    gitlab = 'gitlab'
    gitea = 'gitea'
    bitbucket = 'bitbucket'
    local = 'local'

    class Config:
        use_enum_values = True


class ListRepositoryFilters(BaseModel):
    name__like: Optional[str] = None
    path__like: Optional[str] = None
    version: Optional[str] = None
    url: Optional[str] = None
    workspace_id: Optional[int] = None
    source: Optional[RepositorySource] = Field(description="Source of the repository.", default=None)


class CreateRepositoryRequest(BaseModel):
    workspace_id: int = Field(description='Workspace id to create repository')
    source: RepositorySourceRequestEnum = Field(
        description="Source of the repository: github | gitlab | gitea | bitbucket | local",
        default=RepositorySourceRequestEnum.github
    )
    path: str = Field(..., description="Path to the repository, e.g. owner/repo")
    version: str = Field(description="Version (tag) of the repository.")
    url: str = Field(..., description="Full URL of the repository, e.g. https://github.com/owner/repo")
    # Optional credentials for private repositories
    access_token: Optional[str] = Field(
        description="Access token for private repositories. Leave empty to use workspace-level token.",
        default=None
    )


class PatchRepositoryRequest(BaseModel):
    version: str = Field(pattern=r'((^\d+\.\d+\.\d+$))', description="Version of the repository.")
