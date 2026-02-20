"""
ci_provider.py

Fetch the latest GitHub Actions workflow run status for a repository
using the GitHub REST API via the ``requests`` library.
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class CIProviderError(Exception):
    """Raised when a CI provider operation fails."""


class CIProvider:
    """Read-only client for querying GitHub Actions workflow status."""

    def __init__(
        self, repo_owner: str, repo_name: str, github_token: str
    ) -> None:
        """
        Initialise the CI provider.

        Args:
            repo_owner:   GitHub organisation or user name.
            repo_name:    Repository name.
            github_token: Personal-access or fine-grained token with
                          ``actions:read`` scope.
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self._headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        logger.info(
            "CIProvider initialised for %s/%s", repo_owner, repo_name
        )

    # ── Public API ───────────────────────────────────────────────────

    def get_latest_workflow_status(self, branch: Optional[str] = None) -> dict:
        """
        Return the status and conclusion of the most recent workflow run.

        Returns:
            A dict with keys:
                - status (str):            e.g. "completed", "in_progress", "queued"
                - conclusion (str | None): e.g. "success", "failure", None
                - error (str | None):      Error message if the request failed

        Raises:
            CIProviderError: On unrecoverable API or network failures.
        """
        url = (
            f"{GITHUB_API_BASE}/repos/"
            f"{self.repo_owner}/{self.repo_name}/actions/runs"
        )
        params = {"per_page": 1}
        if branch:
            params["branch"] = branch

        try:
            response = requests.get(
                url, headers=self._headers, params=params, timeout=30
            )
            response.raise_for_status()

        except requests.ConnectionError as exc:
            msg = f"Network error while contacting GitHub API: {exc}"
            logger.error(msg)
            raise CIProviderError(msg) from exc

        except requests.Timeout as exc:
            msg = "GitHub API request timed out."
            logger.error(msg)
            raise CIProviderError(msg) from exc

        except requests.HTTPError as exc:
            msg = (
                f"GitHub API returned HTTP {response.status_code}: "
                f"{response.text}"
            )
            logger.error(msg)
            raise CIProviderError(msg) from exc

        # ── Parse response ───────────────────────────────────────────
        data = response.json()
        runs = data.get("workflow_runs", [])

        if not runs:
            logger.warning(
                "No workflow runs found for %s/%s.",
                self.repo_owner,
                self.repo_name,
            )
            return {
                "status": "none",
                "conclusion": None,
            }

        latest = runs[0]
        status: str = latest.get("status", "unknown")
        conclusion: Optional[str] = latest.get("conclusion")

        logger.info(
            "Latest run – status: %s, conclusion: %s", status, conclusion
        )

        return {
            "status": status,
            "conclusion": conclusion,
            "run_id": latest.get("id"),
        }

    def get_workflow_logs(self, branch: Optional[str] = None) -> str:
        """
        Fetch logs from the latest workflow run.

        Args:
            branch: Optional branch name to filter runs.

        Returns:
            Combined logs from all jobs in the workflow run as a string.

        Raises:
            CIProviderError: On unrecoverable API or network failures.
        """
        # First get the latest workflow run
        status_info = self.get_latest_workflow_status(branch=branch)
        run_id = status_info.get("run_id")
        
        if not run_id:
            logger.warning("No workflow run ID found")
            return ""
        
        # Get jobs for this run
        jobs_url = (
            f"{GITHUB_API_BASE}/repos/"
            f"{self.repo_owner}/{self.repo_name}/actions/runs/{run_id}/jobs"
        )
        
        try:
            response = requests.get(
                jobs_url, headers=self._headers, timeout=30
            )
            response.raise_for_status()
            jobs_data = response.json()
            
            all_logs = []
            jobs = jobs_data.get("jobs", [])
            
            for job in jobs:
                job_id = job.get("id")
                if not job_id:
                    continue
                
                # Get logs for each job
                logs_url = (
                    f"{GITHUB_API_BASE}/repos/"
                    f"{self.repo_owner}/{self.repo_name}/actions/jobs/{job_id}/logs"
                )
                
                try:
                    log_response = requests.get(
                        logs_url, headers=self._headers, timeout=30
                    )
                    if log_response.status_code == 200:
                        all_logs.append(log_response.text)
                except Exception as e:
                    logger.warning(f"Failed to fetch logs for job {job_id}: {e}")
                    continue
            
            combined_logs = "\n".join(all_logs)
            logger.info(f"Fetched {len(combined_logs)} characters of CI logs")
            return combined_logs
            
        except requests.HTTPError as exc:
            msg = f"Failed to fetch workflow logs: {exc}"
            logger.error(msg)
            return ""
        except Exception as exc:
            logger.error(f"Error fetching workflow logs: {exc}")
            return ""
