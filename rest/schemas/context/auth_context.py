from pydantic import BaseModel, Field
from typing import Optional, List


class WorkspaceAuthorizerData(BaseModel):
    id: int
    name: str
    # Generic git platform access token (replaces github_access_token)
    git_access_token: Optional[str] = None
    git_platform_url: Optional[str] = None
    git_platform_type: Optional[str] = None
    git_username: Optional[str] = None
    user_permission: str

    # Legacy property for backward compatibility
    @property
    def github_access_token(self) -> Optional[str]:
        return self.git_access_token

    @github_access_token.setter
    def github_access_token(self, value: Optional[str]):
        self.git_access_token = value


class AuthorizationContextData(BaseModel):
    user_id: int = Field(title='User id')
    workspace: Optional[WorkspaceAuthorizerData] = Field(title='Workspace', default=None)
