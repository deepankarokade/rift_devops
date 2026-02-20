"""Module for cloning or loading Git repositories using GitPython."""

import logging
import os

from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError

logger = logging.getLogger(__name__)


def clone_or_load_repo(repo_url: str, local_path: str) -> Repo:
    """Clone a remote repository or load an existing local one.

    If ``local_path`` does not exist the repository is cloned from
    ``repo_url``.  If the path already exists it is opened as an
    existing Git repository.  The function never performs an automatic
    checkout of any branch (e.g. ``main``).

    Args:
        repo_url: The URL of the remote Git repository to clone.
        local_path: The local filesystem path where the repository
            should reside.

    Returns:
        A ``git.Repo`` instance representing the repository.

    Raises:
        ValueError: If ``repo_url`` or ``local_path`` is empty or
            whitespace-only.
        GitCommandError: If the clone operation fails (e.g. network
            error, invalid URL).
        InvalidGitRepositoryError: If ``local_path`` exists but is not
            a valid Git repository.
    """
    if not isinstance(repo_url, str) or not repo_url.strip():
        raise ValueError("repo_url must be a non-empty string.")
    if not isinstance(local_path, str) or not local_path.strip():
        raise ValueError("local_path must be a non-empty string.")

    local_path = os.path.abspath(local_path)

    if os.path.exists(local_path):
        logger.info("Path '%s' exists — loading existing repository.", local_path)
        try:
            repo = Repo(local_path)
        except InvalidGitRepositoryError:
            logger.error("'%s' is not a valid Git repository.", local_path)
            raise
        except NoSuchPathError:
            logger.error("Path '%s' could not be accessed.", local_path)
            raise
        logger.info("Repository loaded successfully from '%s'.", local_path)
        return repo

    logger.info("Path '%s' does not exist — cloning from '%s'.", local_path, repo_url)
    try:
        repo = Repo.clone_from(
            url=repo_url,
            to_path=local_path,
            no_checkout=True,
        )
    except GitCommandError as exc:
        logger.error(
            "Failed to clone repository from '%s' to '%s': %s",
            repo_url,
            local_path,
            exc,
        )
        raise
    logger.info("Repository cloned successfully to '%s'.", local_path)
    return repo
