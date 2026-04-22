"""
Generic Git platform client.

Supports:
  - GitHub  (github.com or GitHub Enterprise via base_url)
  - GitLab  (gitlab.com or self-hosted)
  - Gitea   (self-hosted Gitea / Forgejo)
  - Bitbucket Cloud
  - Any other platform via generic HTTP (read-only fallback)

Authentication methods (per platform):
  - token / personal access token
  - username + password (HTTP Basic)
  - SSH private key (for git operations via subprocess)
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Optional
from urllib.parse import urlparse, urljoin

import requests

from core.logger import get_configured_logger
from schemas.exceptions.base import (
    ResourceNotFoundException,
    ForbiddenException,
    UnauthorizedException,
    BaseException as DominoBaseException,
)


def _detect_platform(url: str) -> str:
    """Heuristic platform detection from URL."""
    host = urlparse(url).hostname or ""
    if "github" in host:
        return "github"
    if "gitlab" in host:
        return "gitlab"
    if "bitbucket" in host:
        return "bitbucket"
    # Default to gitea for self-hosted instances; can be overridden
    return "gitea"


class GitPlatformClient:
    """
    Unified client for reading repository metadata (tags, file contents) from
    multiple Git hosting platforms.

    Parameters
    ----------
    platform_url : str
        The base URL of the platform, e.g. ``https://github.com``,
        ``https://gitlab.mycompany.com``, ``http://gitea.local:3000``.
    token : str or None
        Personal access token (or app token) for authentication.
    username : str or None
        Username for HTTP Basic auth (Gitea, Bitbucket, …).
    password : str or None
        Password for HTTP Basic auth.
    platform_type : str or None
        Override auto-detection.  One of ``github``, ``gitlab``, ``gitea``,
        ``bitbucket``.
    """

    def __init__(
        self,
        platform_url: str = "https://github.com",
        token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        platform_type: Optional[str] = None,
        ssl_verify: bool = True,
    ):
        self.platform_url = platform_url.rstrip("/")
        self.token = token.strip() if token else None
        self.username = username
        self.password = password
        self.ssl_verify = ssl_verify
        self.platform_type = platform_type or _detect_platform(platform_url)
        self.logger = get_configured_logger(self.__class__.__name__)

        self._session = requests.Session()
        self._session.verify = ssl_verify
        self._configure_auth()

    # ------------------------------------------------------------------
    # Auth setup
    # ------------------------------------------------------------------

    def _configure_auth(self):
        if self.token:
            if self.platform_type == "github":
                self._session.headers["Authorization"] = f"Bearer {self.token}"
            elif self.platform_type == "gitlab":
                self._session.headers["PRIVATE-TOKEN"] = self.token
            elif self.platform_type in ("gitea", "forgejo"):
                self._session.headers["Authorization"] = f"token {self.token}"
            elif self.platform_type == "bitbucket":
                # Bitbucket uses HTTP Basic with token as password when using
                # app passwords; set via auth tuple below
                if self.username:
                    self._session.auth = (self.username, self.token)
                else:
                    self._session.headers["Authorization"] = f"Bearer {self.token}"
        elif self.username and self.password:
            self._session.auth = (self.username, self.password)

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, url: str, **kwargs) -> requests.Response:
        try:
            resp = self._session.get(url, **kwargs)
        except requests.exceptions.ConnectionError as exc:
            self.logger.error("Connection error: %s", exc)
            raise DominoBaseException(f"Cannot connect to git platform at {self.platform_url}")
        self._raise_for_status(resp, url)
        return resp

    def _raise_for_status(self, resp: requests.Response, url: str):
        if resp.status_code == 404:
            raise ResourceNotFoundException(f"Resource not found: {url}")
        if resp.status_code in (401,):
            raise UnauthorizedException("Git platform: invalid credentials.")
        if resp.status_code in (403,):
            raise ForbiddenException("Git platform: access denied. Check token/permissions.")
        if not resp.ok:
            raise DominoBaseException(
                f"Git platform error {resp.status_code} for {url}: {resp.text[:200]}"
            )

    # ------------------------------------------------------------------
    # API base URL helpers
    # ------------------------------------------------------------------

    def _api_base(self) -> str:
        if self.platform_type == "github":
            # If this is github.com use api.github.com; otherwise assume GHE
            if "github.com" in self.platform_url:
                return "https://api.github.com"
            return f"{self.platform_url}/api/v3"
        if self.platform_type == "gitlab":
            return f"{self.platform_url}/api/v4"
        if self.platform_type in ("gitea", "forgejo"):
            return f"{self.platform_url}/api/v1"
        if self.platform_type == "bitbucket":
            return "https://api.bitbucket.org/2.0"
        return self.platform_url

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_tags(self, repo_path: str) -> list[dict]:
        """
        Return list of tags for *repo_path* (``owner/repo``).

        Returns list of dicts with keys: ``name``, ``commit_sha``.
        """
        if self.platform_type == "github":
            return self._github_get_tags(repo_path)
        if self.platform_type == "gitlab":
            return self._gitlab_get_tags(repo_path)
        if self.platform_type in ("gitea", "forgejo"):
            return self._gitea_get_tags(repo_path)
        if self.platform_type == "bitbucket":
            return self._bitbucket_get_tags(repo_path)
        raise DominoBaseException(f"Unsupported platform type: {self.platform_type}")

    def get_tag(self, repo_path: str, tag_name: str) -> Optional[dict]:
        """Return a single tag dict or None if not found."""
        tags = self.get_tags(repo_path)
        for tag in tags:
            if tag["name"] == tag_name:
                return tag
        return None

    def get_file_content(self, repo_path: str, file_path: str, ref: str = "HEAD") -> bytes:
        """
        Fetch raw file bytes at *file_path* in *repo_path* at git ref *ref*.
        """
        if self.platform_type == "github":
            return self._github_get_file(repo_path, file_path, ref)
        if self.platform_type == "gitlab":
            return self._gitlab_get_file(repo_path, file_path, ref)
        if self.platform_type in ("gitea", "forgejo"):
            return self._gitea_get_file(repo_path, file_path, ref)
        if self.platform_type == "bitbucket":
            return self._bitbucket_get_file(repo_path, file_path, ref)
        raise DominoBaseException(f"Unsupported platform type: {self.platform_type}")

    def create_file(self, repo_path: str, file_path: str, content: str, branch: str = "main", message: str = "Create file") -> None:
        """Create or update a file in the remote repository."""
        if self.platform_type == "github":
            self._github_create_file(repo_path, file_path, content, branch, message)
        elif self.platform_type == "gitlab":
            self._gitlab_create_file(repo_path, file_path, content, branch, message)
        elif self.platform_type in ("gitea", "forgejo"):
            self._gitea_create_file(repo_path, file_path, content, branch, message)
        elif self.platform_type == "bitbucket":
            self._bitbucket_create_file(repo_path, file_path, content, branch, message)
        else:
            raise DominoBaseException(f"Unsupported platform type: {self.platform_type}")

    def delete_file(self, repo_path: str, file_path: str, branch: str = "main", message: str = "Delete file") -> None:
        """Delete a file from the remote repository."""
        if self.platform_type == "github":
            self._github_delete_file(repo_path, file_path, branch, message)
        elif self.platform_type == "gitlab":
            self._gitlab_delete_file(repo_path, file_path, branch, message)
        elif self.platform_type in ("gitea", "forgejo"):
            self._gitea_delete_file(repo_path, file_path, branch, message)
        else:
            raise DominoBaseException(f"Delete not supported for platform: {self.platform_type}")

    # ------------------------------------------------------------------
    # GitHub implementation
    # ------------------------------------------------------------------

    def _github_get_tags(self, repo_path: str) -> list[dict]:
        url = f"{self._api_base()}/repos/{repo_path}/tags"
        tags = []
        page = 1
        while True:
            resp = self._get(url, params={"per_page": 100, "page": page})
            data = resp.json()
            if not data:
                break
            for item in data:
                tags.append({
                    "name": item["name"],
                    "commit_sha": item["commit"]["sha"],
                    "last_modified": None,
                })
            if len(data) < 100:
                break
            page += 1
        return tags

    def _github_get_file(self, repo_path: str, file_path: str, ref: str) -> bytes:
        url = f"{self._api_base()}/repos/{repo_path}/contents/{file_path}"
        resp = self._get(url, params={"ref": ref})
        data = resp.json()
        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data["content"])
        raise DominoBaseException(f"Unexpected file response format from GitHub: {data}")

    def _github_create_file(self, repo_path, file_path, content, branch, message):
        url = f"{self._api_base()}/repos/{repo_path}/contents/{file_path}"
        # Check if file exists (to get sha for update)
        sha = None
        try:
            resp = self._get(url, params={"ref": branch})
            sha = resp.json().get("sha")
        except ResourceNotFoundException:
            pass
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha
        resp = self._session.put(url, json=payload)
        self._raise_for_status(resp, url)

    def _github_delete_file(self, repo_path, file_path, branch, message):
        url = f"{self._api_base()}/repos/{repo_path}/contents/{file_path}"
        resp = self._get(url, params={"ref": branch})
        sha = resp.json().get("sha")
        payload = {"message": message, "sha": sha, "branch": branch}
        resp = self._session.delete(url, json=payload)
        self._raise_for_status(resp, url)

    # ------------------------------------------------------------------
    # GitLab implementation
    # ------------------------------------------------------------------

    def _gitlab_project_id(self, repo_path: str) -> str:
        """URL-encode path for GitLab API."""
        return repo_path.replace("/", "%2F")

    def _gitlab_get_tags(self, repo_path: str) -> list[dict]:
        pid = self._gitlab_project_id(repo_path)
        url = f"{self._api_base()}/projects/{pid}/repository/tags"
        tags = []
        page = 1
        while True:
            resp = self._get(url, params={"per_page": 100, "page": page})
            data = resp.json()
            if not data:
                break
            for item in data:
                tags.append({
                    "name": item["name"],
                    "commit_sha": item["commit"]["id"],
                    "last_modified": item["commit"].get("committed_date"),
                })
            if len(data) < 100:
                break
            page += 1
        return tags

    def _gitlab_get_file(self, repo_path: str, file_path: str, ref: str) -> bytes:
        pid = self._gitlab_project_id(repo_path)
        encoded_path = file_path.replace("/", "%2F")
        url = f"{self._api_base()}/projects/{pid}/repository/files/{encoded_path}/raw"
        resp = self._get(url, params={"ref": ref})
        return resp.content

    def _gitlab_create_file(self, repo_path, file_path, content, branch, message):
        pid = self._gitlab_project_id(repo_path)
        encoded_path = file_path.replace("/", "%2F")
        url = f"{self._api_base()}/projects/{pid}/repository/files/{encoded_path}"
        payload = {
            "branch": branch,
            "content": content,
            "commit_message": message,
            "encoding": "text",
        }
        # Try create first, fall back to update
        resp = self._session.post(url, json=payload)
        if resp.status_code == 400:
            resp = self._session.put(url, json=payload)
        self._raise_for_status(resp, url)

    def _gitlab_delete_file(self, repo_path, file_path, branch, message):
        pid = self._gitlab_project_id(repo_path)
        encoded_path = file_path.replace("/", "%2F")
        url = f"{self._api_base()}/projects/{pid}/repository/files/{encoded_path}"
        payload = {"branch": branch, "commit_message": message}
        resp = self._session.delete(url, json=payload)
        self._raise_for_status(resp, url)

    # ------------------------------------------------------------------
    # Gitea / Forgejo implementation
    # ------------------------------------------------------------------

    def _gitea_get_tags(self, repo_path: str) -> list[dict]:
        owner, repo = repo_path.split("/", 1)
        url = f"{self._api_base()}/repos/{owner}/{repo}/tags"
        resp = self._get(url, params={"limit": 50, "page": 1})
        data = resp.json()
        return [
            {
                "name": item["name"],
                "commit_sha": item["commit"]["sha"],
                "last_modified": item["commit"].get("created"),
            }
            for item in data
        ]

    def _gitea_get_file(self, repo_path: str, file_path: str, ref: str) -> bytes:
        owner, repo = repo_path.split("/", 1)
        url = f"{self._api_base()}/repos/{owner}/{repo}/contents/{file_path}"
        resp = self._get(url, params={"ref": ref})
        data = resp.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"])
        return data.get("content", "").encode()

    def _gitea_create_file(self, repo_path, file_path, content, branch, message):
        owner, repo = repo_path.split("/", 1)
        url = f"{self._api_base()}/repos/{owner}/{repo}/contents/{file_path}"
        # Check if exists
        sha = None
        try:
            resp = self._get(url, params={"ref": branch})
            sha = resp.json().get("sha")
        except ResourceNotFoundException:
            pass
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
            "new_branch": branch,
        }
        if sha:
            payload["sha"] = sha
            resp = self._session.put(url, json=payload)
        else:
            resp = self._session.post(url, json=payload)
        self._raise_for_status(resp, url)

    def _gitea_delete_file(self, repo_path, file_path, branch, message):
        owner, repo = repo_path.split("/", 1)
        url = f"{self._api_base()}/repos/{owner}/{repo}/contents/{file_path}"
        resp = self._get(url, params={"ref": branch})
        sha = resp.json().get("sha")
        payload = {"message": message, "sha": sha, "branch": branch}
        resp = self._session.delete(url, json=payload)
        self._raise_for_status(resp, url)

    # ------------------------------------------------------------------
    # Bitbucket Cloud implementation
    # ------------------------------------------------------------------

    def _bitbucket_get_tags(self, repo_path: str) -> list[dict]:
        url = f"{self._api_base()}/repositories/{repo_path}/refs/tags"
        tags = []
        while url:
            resp = self._get(url, params={"pagelen": 100})
            data = resp.json()
            for item in data.get("values", []):
                tags.append({
                    "name": item["name"],
                    "commit_sha": item["target"]["hash"],
                    "last_modified": item["target"].get("date"),
                })
            url = data.get("next")
        return tags

    def _bitbucket_get_file(self, repo_path: str, file_path: str, ref: str) -> bytes:
        url = f"{self._api_base()}/repositories/{repo_path}/src/{ref}/{file_path}"
        resp = self._get(url)
        return resp.content

    def _bitbucket_create_file(self, repo_path, file_path, content, branch, message):
        url = f"{self._api_base()}/repositories/{repo_path}/src"
        # Bitbucket uses multipart form data for file creation
        resp = self._session.post(
            url,
            data={
                "message": message,
                "branch": branch,
                file_path: content,
            }
        )
        self._raise_for_status(resp, url)
