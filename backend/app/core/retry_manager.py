"""
retry_manager.py

Tracks retry attempts for CI pipeline healing and decides whether
a failed workflow should be retried based on its conclusion.
"""

import logging

logger = logging.getLogger(__name__)


class RetryManager:
    """Manages retry logic with a configurable maximum attempt count."""

    def __init__(self, max_retries: int = 2) -> None:
        """
        Initialise the retry manager.

        Args:
            max_retries: Maximum number of retry attempts allowed.
        """
        self.max_retries = max_retries
        self._attempts: int = 0
        logger.info("RetryManager initialised (max_retries=%d)", max_retries)

    def should_retry(self, conclusion: str) -> bool:
        """
        Determine whether a retry is warranted.

        A retry is allowed only when the conclusion is ``"failure"``
        **and** the attempt limit has not been exceeded.

        Args:
            conclusion: Workflow run conclusion (e.g. "success", "failure").

        Returns:
            True if a retry should be performed, False otherwise.
        """
        if conclusion is None or conclusion != "failure":
            logger.info(
                "No retry needed – conclusion is '%s'.", conclusion
            )
            return False

        if self.has_exceeded():
            logger.warning(
                "Retry limit reached (%d/%d). Will not retry.",
                self._attempts,
                self.max_retries,
            )
            return False

        logger.info(
            "Retry approved (%d/%d attempts used).",
            self._attempts,
            self.max_retries,
        )
        return True

    def track_attempt(self) -> None:
        """Increment the internal retry counter by one."""
        self._attempts += 1
        logger.info(
            "Attempt tracked: %d/%d", self._attempts, self.max_retries
        )

    def has_exceeded(self) -> bool:
        """
        Check whether the maximum number of retries has been reached.

        Returns:
            True if attempts >= max_retries, False otherwise.
        """
        return self._attempts >= self.max_retries
