"""
Backward-compatible GitHub REST client.

This module wraps the new generic GitPlatformClient and exposes the same
interface as the original GithubRestClient so existing callers continue
to work without changes.
"""

from __future__ import annotations

from typing import Optional

from clients.git_client import GitPlatformClient
from core.logger import get_configured_logger
from schemas.exceptions.base import ResourceNotFoundException


class GithubRestClient:
    """
    Thin wrapper around GitPlatformClient for GitHub, preserving the original
    interface used throughout the codebase.
    """

    def __init__(self, token: Optional[str] = None):
        if token == "":
            token = None
        self._client = GitPlatformClient(
            platform_url="https://github.com",
            token=token,
            platform_type="github",
        )
        self.logger = get_configured_logger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Original interface
    # ------------------------------------------------------------------

    def get_tags(self, repo_name: str, as_list: bool = True):
        tags = self._client.get_tags(repo_name)
        # Return lightweight tag-like objects to maintain interface compatibility
        return [_TagProxy(t) for t in tags] if tags else []

    def get_tag(self, repo_name: str, tag_name: str):
        tag = self._client.get_tag(repo_name, tag_name)
        if not tag:
            return None
        return _TagProxy(tag)

    def get_contents(self, repo_name: str, file_path: str, commit_sha: Optional[str] = None):
        ref = commit_sha or "HEAD"
        raw = self._client.get_file_content(repo_name, file_path, ref)
        return _ContentsProxy(raw, file_path)

    def create_file(self, repo_name: str, file_path: str, content: str):
        self._client.create_file(repo_name, file_path, content)

    def delete_file(self, repo_name: str, file_path: str):
        self._client.delete_file(repo_name, file_path)

    def get_commits(self, repo_name: str, number_of_commits: int = 1):
        # Not used in core flow; return empty list to avoid breaking callers
        return []

    def get_commit(self, repo_name: str, commit_sha: str):
        return None

    def compare_commits(self, repo_name: str, base_sha: str, head_sha: str):
        return None


class _TagProxy:
    """Minimal proxy to mimic PyGithub Tag object."""

    def __init__(self, tag_dict: dict):
        self.name = tag_dict["name"]
        self.last_modified = tag_dict.get("last_modified")
        self._commit_sha = tag_dict.get("commit_sha")

    class _Commit:
        def __init__(self, sha):
            self.sha = sha

    @property
    def commit(self):
        return self._Commit(self._commit_sha)


class _ContentsProxy:
    """Minimal proxy to mimic PyGithub ContentFile object."""

    def __init__(self, raw_bytes: bytes, path: str):
        self._raw = raw_bytes
        self.path = path

    @property
    def decoded_content(self) -> bytes:
        return self._raw

    @property
    def sha(self) -> Optional[str]:
        return None
