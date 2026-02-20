"""
github_client.py

Git operations client built on GitPython.
Provides safe branch creation, committing, and pushing while
ensuring the ``main`` branch is never checked out or pushed to.
"""

import logging
from git import Repo, InvalidGitRepositoryError, GitCommandError

logger = logging.getLogger(__name__)

COMMIT_PREFIX = "[AI-AGENT]"
PROTECTED_BRANCHES = {"main", "master"}


class BranchProtectionError(Exception):
    """Raised when an operation targets a protected branch."""


class GitHubClient:
    """Thin wrapper around a local Git repository for safe AI-driven workflows."""

    def __init__(self, repo_path: str) -> None:
        """
        Initialise the client by opening an existing local repository.

        Args:
            repo_path: Absolute path to the local git repository.

        Raises:
            InvalidGitRepositoryError: If the path is not a valid git repo.
        """
        try:
            self.repo = Repo(repo_path)
            logger.info("Opened repository at: %s", repo_path)
        except InvalidGitRepositoryError:
            logger.error("Invalid git repository: %s", repo_path)
            raise

    # ── Guards ───────────────────────────────────────────────────────

    def _assert_not_protected(self) -> None:
        """Raise if the active branch is a protected branch."""
        current = self.repo.active_branch.name
        if current in PROTECTED_BRANCHES:
            msg = (
                f"Operation blocked: current branch '{current}' is protected. "
                "Switch to a feature branch first."
            )
            logger.error(msg)
            raise BranchProtectionError(msg)

    # ── Public API ───────────────────────────────────────────────────

    def create_branch(self, branch_name: str) -> None:
        """
        Create and checkout a new branch from the current HEAD.

        Args:
            branch_name: Name for the new branch.

        Raises:
            BranchProtectionError: If *branch_name* matches a protected branch.
            GitCommandError: On any underlying git failure.
        """
        if branch_name in PROTECTED_BRANCHES:
            msg = f"Cannot create or checkout protected branch '{branch_name}'."
            logger.error(msg)
            raise BranchProtectionError(msg)

        try:
            new_branch = self.repo.create_head(branch_name)
            new_branch.checkout()
            logger.info("Created and checked out branch: %s", branch_name)
        except GitCommandError as exc:
            logger.error("Failed to create branch '%s': %s", branch_name, exc)
            raise

    def commit_all(self, message: str) -> None:
        """
        Stage all changes and commit with an auto-prefixed message.

        The commit message is automatically prefixed with ``[AI-AGENT]``.

        Args:
            message: Descriptive commit message (prefix is added automatically).

        Raises:
            BranchProtectionError: If the current branch is protected.
            GitCommandError: On any underlying git failure.
        """
        self._assert_not_protected()

        try:
            self.repo.git.add(A=True)

            if not self.repo.index.diff("HEAD") and not self.repo.untracked_files:
                logger.warning("Nothing to commit – working tree is clean.")
                return

            full_message = f"{COMMIT_PREFIX} {message}"
            self.repo.index.commit(full_message)
            logger.info("Committed: %s", full_message)
        except GitCommandError as exc:
            logger.error("Commit failed: %s", exc)
            raise

    def push_current_branch(self) -> None:
        """
        Push the current branch to the ``origin`` remote.

        Raises:
            BranchProtectionError: If the current branch is protected.
            GitCommandError: On any underlying git failure.
        """
        self._assert_not_protected()

        branch = self.repo.active_branch.name
        try:
            origin = self.repo.remote(name="origin")
            origin.push(refspec=f"{branch}:{branch}")
            logger.info("Pushed branch '%s' to origin.", branch)
        except GitCommandError as exc:
            logger.error("Push failed for branch '%s': %s", branch, exc)
            raise
