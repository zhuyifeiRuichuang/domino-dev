import { type Roles } from "@utils/roles";

export enum repositorySource {
  github = "github",
  gitlab = "gitlab",
  gitea = "gitea",
  bitbucket = "bitbucket",
  local = "local",
}

export enum workspaceStatus {
  PENDING = "pending",
  ACCEPTED = "accepted",
  REJECTED = "rejected",
}

export interface WorkspaceSummary {
  id: string;
  workspace_name: string;
  user_permission: Roles;
  status: workspaceStatus;
  /** @deprecated Use git_access_token_filled */
  github_access_token_filled: boolean;
  git_access_token_filled?: boolean;
  git_platform_type?: string;
  git_platform_url?: string;
  git_username?: string;
}
