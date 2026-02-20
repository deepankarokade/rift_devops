"""
git_committer.py

Agent node responsible for committing and pushing AI-generated fixes.
Uses GitHubClient for all git operations and enforces branch safety.
"""

import logging

from app.integrations.github_client import GitHubClient
from app.core.database import create_fix, SessionLocal

logger = logging.getLogger(__name__)

# Commit message prefix
COMMIT_PREFIX = "[AI-AGENT]"


class NoChangesDetectedError(Exception):
    """Raised when there are no staged or unstaged changes to commit."""


def commit_fix(repo_path: str, message: str, branch_name: str = None) -> None:
    """
    Stage all changes, commit with a prefixed message, and push.

    The commit message is automatically formatted as::

        [AI-AGENT] Fix SYNTAX error in file line X

    where *message* supplies the descriptive portion.

    Args:
        repo_path: Absolute path to the local git repository.
        message:   Descriptive part of the commit message
                   (the ``[AI-AGENT]`` prefix is added by GitHubClient).
        branch_name: Optional branch name to use (from state)

    Raises:
        NoChangesDetectedError: If the working tree has no changes.
        BranchProtectionError:  If the current branch is ``main`` or ``master``.
        GitCommandError:        On any underlying git failure.
    """
    from datetime import datetime
    client = GitHubClient(repo_path)
    repo = client.repo

    # ── Verify there are actual changes to commit ────────────────────
    if not repo.is_dirty(untracked_files=True):
        msg = "No changes detected in the working tree. Nothing to commit."
        logger.error(msg)
        raise NoChangesDetectedError(msg)

    logger.info("Changes detected – preparing commit.")

    # ── Stage all changes first (including untracked files) ──────────
    try:
        repo.git.add(A=True)
        logger.info("Staged all changes including untracked files")
    except Exception as e:
        logger.error(f"Failed to stage changes: {e}")
        raise

    # ── Auto-create feature branch if on protected branch ────────────
    current_branch = repo.active_branch.name
    if current_branch in {"main", "master"}:
        # Use provided branch name or create timestamp-based one
        if branch_name:
            feature_branch = branch_name
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            feature_branch = f"ai-fix-{timestamp}"
        
        try:
            # Check if branch already exists
            existing_branches = [b.name for b in repo.branches]
            if feature_branch in existing_branches:
                logger.info(f"Branch '{feature_branch}' already exists, checking out")
                repo.git.checkout(feature_branch)
            else:
                # Create branch without checking out (to avoid untracked file issues)
                new_branch = repo.create_head(feature_branch)
                # Now checkout the new branch (files are already staged)
                new_branch.checkout()
                logger.info(f"Created and checked out feature branch '{feature_branch}'")
        except Exception as e:
            logger.error(f"Failed to create/checkout feature branch: {e}")
            raise

    # ── Commit the staged changes ────────────────────────────────────
    try:
        full_message = f"{COMMIT_PREFIX} {message}"
        repo.index.commit(full_message)
        logger.info("Committed: %s", full_message)
    except Exception as exc:
        logger.error("Commit failed: %s", exc)
        raise

    # ── Push to remote ───────────────────────────────────────────────
    client.push_current_branch()
    logger.info("Changes pushed to remote.")


def run(state):
    """Commit and push fixes to the repository, and save fix records to database."""
    repo_path = state.get("repo_path", ".")
    message = state.get("commit_message", "Automated fix applied")
    branch_name = state.get("branch_name", "")
    logs = list(state.get("logs") or [])
    
    try:
        commit_fix(repo_path, message, branch_name)
        state["commit_count"] = state.get("commit_count", 0) + 1
        logs.append("Changes committed and pushed")
        state["logs"] = logs
        
        # Save fix records to database
        run_id = state.get("run_id")
        classified_failures = state.get("classified_failures", [])
        if run_id and classified_failures:
            db = SessionLocal()
            try:
                for failure in classified_failures:
                    # Parse the classified failure string
                    parts = failure.split(" ")
                    bug_type = parts[0] if parts else "SYNTAX"
                    file_path = ""
                    line_number = None
                    
                    # Try to extract file and line from format: "BUG_TYPE error in file line N"
                    if "error in" in failure and "line" in failure:
                        try:
                            after_in = failure.split("error in ")[1]
                            file_line = after_in.split(" line ")
                            file_path = file_line[0].strip()
                            line_str = file_line[1].split(" ")[0].strip()
                            line_number = int(line_str) if line_str.isdigit() else None
                        except (IndexError, ValueError):
                            pass
                    
                    create_fix(
                        db=db,
                        run_id=run_id,
                        file=file_path or "unknown",
                        bug_type=bug_type if bug_type in ["LINTING", "SYNTAX", "LOGIC", "TYPE_ERROR", "IMPORT", "INDENTATION"] else "SYNTAX",
                        line_number=line_number,
                        commit_message=f"[AI-AGENT] {message}",
                        status="FIXED"
                    )
            except Exception as e:
                logger.error("Failed to save fix to database: %s", e)
                db.rollback()
            finally:
                db.close()
                
    except Exception as e:
        logs.append(f"Commit failed: {str(e)}")
        state["logs"] = logs
        
        # Save failed fix to database
        run_id = state.get("run_id")
        if run_id:
            db = SessionLocal()
            try:
                create_fix(
                    db=db,
                    run_id=run_id,
                    file="unknown",
                    bug_type="SYNTAX",
                    status="FAILED"
                )
            except Exception as db_err:
                logger.error("Failed to save failed fix to database: %s", db_err)
                db.rollback()
            finally:
                db.close()
    
    return state
