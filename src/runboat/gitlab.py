import logging
from enum import Enum
from typing import Any
from urllib.parse import quote

import httpx

from .exceptions import NotFoundOnGitLab
from .github import CommitInfo
from .settings import settings

_logger = logging.getLogger(__name__)


async def _gitlab_request(method: str, url: str, json: Any = None) -> Any:
    async with httpx.AsyncClient() as client:
        full_url = f"{settings.gitlab_url}/api/v4{url}"
        headers: dict[str, str] = {}
        if settings.gitlab_token:
            # Support both OAuth/Bearer tokens and personal access tokens
            headers["Authorization"] = f"Bearer {settings.gitlab_token}"
        response = await client.request(method, full_url, headers=headers, json=json)
        if response.status_code == 404:
            raise NotFoundOnGitLab(f"GitLab URL not found: {full_url}.")
        response.raise_for_status()
        return response.json()


async def get_branch_info(
    repo: str, branch: str, project_id: str | None = None
) -> CommitInfo:
    if project_id:
        branch_data = await _gitlab_request(
            "GET",
            f"/projects/{project_id}/repository/branches/{quote(branch, safe='')}",
        )
    else:
        encoded_repo = quote(repo, safe="")
        branch_data = await _gitlab_request(
            "GET",
            f"/projects/{encoded_repo}/repository/branches/{quote(branch, safe='')}",
        )
    return CommitInfo(
        repo=repo,
        target_branch=branch,
        pr=None,
        git_commit=branch_data["commit"]["id"],
        platform="gitlab",
        project_id=project_id,
    )


async def get_merge_request_info(
    repo: str, mr_iid: int, project_id: str | None = None
) -> CommitInfo:
    pid = project_id or quote(repo, safe="")
    mr_data = await _gitlab_request(
        "GET",
        f"/projects/{pid}/merge_requests/{mr_iid}",
    )
    return CommitInfo(
        repo=repo,
        target_branch=mr_data["target_branch"],
        pr=mr_iid,
        git_commit=mr_data["sha"],
        platform="gitlab",
        project_id=project_id,
    )


class GitLabStatusState(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    canceled = "canceled"


async def notify_status(
    repo: str,
    sha: str,
    state: GitLabStatusState,
    target_url: str | None,
    project_id: str | None = None,
) -> None:
    if settings.disable_commit_statuses:
        return
    pid = project_id or quote(repo, safe="")
    json_payload: dict[str, Any] = {
        "state": state.value,
        "context": "runboat/build",
        "name": "runboat/build",
    }
    if target_url:
        json_payload["target_url"] = target_url
    try:
        await _gitlab_request(
            "POST",
            f"/projects/{pid}/statuses/{sha}",
            json=json_payload,
        )
    except httpx.HTTPStatusError as e:
        _logger.error(
            f"Failed to post GitLab commit status (code {e.response.status_code}):\n"
            f"{e.response.text}"
        )
