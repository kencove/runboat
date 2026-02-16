import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from .controller import controller
from .github import CommitInfo
from .settings import settings

_MR_DEPLOY_ACTIONS = {"open", "reopen", "update"}
_MR_UNDEPLOY_ACTIONS = {"close", "merge"}

_logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_github_signature(
    x_hub_signature_256: str | None, secret: bytes | None, body: bytes
) -> bool:
    if not secret:
        return True
    if not x_hub_signature_256:
        _logger.warning("Got payload without X-Hub-Signature-256")
        return False
    signature = "sha256=" + hmac.new(secret, body, "sha256").hexdigest()
    if not hmac.compare_digest(signature, x_hub_signature_256):
        _logger.warning("Got payload with invalid X-Hub-Signature-256")
        return False
    return True


@router.post("/webhooks/github")
async def receive_payload(
    background_tasks: BackgroundTasks,
    request: Request,
    x_github_event: Annotated[str, Header(...)],
    x_hub_signature_256: Annotated[str | None, Header(...)] = None,
) -> None:
    body = await request.body()
    if not _verify_github_signature(
        x_hub_signature_256, settings.github_webhook_secret, body
    ):
        return
    payload = await request.json()
    if x_github_event == "pull_request":
        repo = payload["repository"]["full_name"]
        target_branch = payload["pull_request"]["base"]["ref"]
        if not settings.is_repo_and_branch_supported(repo, target_branch):
            _logger.debug(
                "Ignoring %s payload for unsupported repo %s or target branch %s",
                x_github_event,
                repo,
                target_branch,
            )
            return
        if payload["action"] in ("opened", "synchronize"):
            background_tasks.add_task(
                controller.deploy_commit,
                CommitInfo(
                    repo=repo,
                    target_branch=target_branch,
                    pr=payload["pull_request"]["number"],
                    git_commit=payload["pull_request"]["head"]["sha"],
                ),
            )
        elif payload["action"] in ("closed",):
            background_tasks.add_task(
                controller.undeploy_builds,
                repo=repo,
                pr=payload["pull_request"]["number"],
            )
    elif x_github_event == "push":
        repo = payload["repository"]["full_name"]
        target_branch = payload["ref"].split("/")[-1]
        if not settings.is_repo_and_branch_supported(repo, target_branch):
            _logger.debug(
                "Ignoring %s payload for unsupported repo %s or target branch %s",
                x_github_event,
                repo,
                target_branch,
            )
            return
        background_tasks.add_task(
            controller.deploy_commit,
            CommitInfo(
                repo=repo,
                target_branch=target_branch,
                pr=None,
                git_commit=payload["after"],
            ),
        )


def _verify_gitlab_token(x_gitlab_token: str | None) -> bool:
    if not settings.gitlab_webhook_token:
        return True
    if not x_gitlab_token:
        _logger.warning("Got GitLab payload without X-Gitlab-Token")
        return False
    if not hmac.compare_digest(x_gitlab_token, settings.gitlab_webhook_token):
        _logger.warning("Got GitLab payload with invalid X-Gitlab-Token")
        return False
    return True


def _gitlab_repo_info(payload: dict) -> tuple[str, str | None]:
    """Extract repo path and project_id from a GitLab webhook payload."""
    repo = payload["project"]["path_with_namespace"]
    project_id = str(payload["project"]["id"])
    return repo, project_id


@router.post("/webhooks/gitlab")
async def receive_gitlab_payload(
    background_tasks: BackgroundTasks,
    request: Request,
    x_gitlab_event: Annotated[str, Header(...)],
    x_gitlab_token: Annotated[str | None, Header(...)] = None,
) -> None:
    if not _verify_gitlab_token(x_gitlab_token):
        raise HTTPException(status_code=403, detail="Invalid X-Gitlab-Token")
    payload = await request.json()
    if x_gitlab_event == "Merge Request Hook":
        repo, project_id = _gitlab_repo_info(payload)
        attrs = payload["object_attributes"]
        action = attrs["action"]
        target_branch = attrs["target_branch"]
        if not settings.is_repo_and_branch_supported(repo, target_branch):
            _logger.debug(
                "Ignoring GitLab MR payload for unsupported repo %s "
                "or target branch %s",
                repo,
                target_branch,
            )
            return
        if action in _MR_DEPLOY_ACTIONS:
            background_tasks.add_task(
                controller.deploy_commit,
                CommitInfo(
                    repo=repo,
                    target_branch=target_branch,
                    pr=attrs["iid"],
                    git_commit=attrs["last_commit"]["id"],
                    platform="gitlab",
                    project_id=project_id,
                ),
            )
        elif action in _MR_UNDEPLOY_ACTIONS:
            background_tasks.add_task(
                controller.undeploy_builds,
                repo=repo,
                pr=attrs["iid"],
            )
    elif x_gitlab_event == "Push Hook":
        repo, project_id = _gitlab_repo_info(payload)
        target_branch = payload["ref"].split("/")[-1]
        if not settings.is_repo_and_branch_supported(repo, target_branch):
            _logger.debug(
                "Ignoring GitLab push payload for unsupported repo %s "
                "or target branch %s",
                repo,
                target_branch,
            )
            return
        background_tasks.add_task(
            controller.deploy_commit,
            CommitInfo(
                repo=repo,
                target_branch=target_branch,
                pr=None,
                git_commit=payload["after"],
                platform="gitlab",
                project_id=project_id,
            ),
        )
