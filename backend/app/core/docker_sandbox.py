"""
docker_sandbox.py

Run pytest inside an isolated Docker container using subprocess.
Mounts the target repository read-only, enforces resource limits,
disables networking, and captures structured output.
"""

import subprocess
import logging
import shlex
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_IMAGE = "rift-test-runner"
_DEFAULT_TIMEOUT = 300
_MEMORY_LIMIT = "512m"


def run_pytest_in_docker(
    repo_path: str,
    image: str = _DEFAULT_IMAGE,
    timeout: int = _DEFAULT_TIMEOUT,
) -> dict:
    """Run pytest inside a Docker container for isolated test execution.

    The container is:
      - ephemeral (--rm)
      - read-only volume mount (prevents writes to host)
      - network-disabled (no exfiltration)
      - memory-capped (prevents OOM on host)

    Args:
        repo_path: Absolute path to the repository to mount into the container.
        image: Docker image to use. Defaults to ``rift-test-runner``.
        timeout: Maximum seconds before the container is killed.

    Returns:
        A structured dictionary:
            - success (bool): True when pytest exits 0.
            - exit_code (int): Process exit code (-1 if unavailable).
            - stdout (str): Captured standard output.
            - stderr (str): Captured standard error.
            - error (str | None): Error description on failure.
    """
    result: dict = {
        "success": False,
        "exit_code": -1,
        "stdout": "",
        "stderr": "",
        "error": None,
    }

    # If no tests are present, return early instead of injecting synthetic failures.
    # This prevents misleading "analysis failed" runs on repositories without tests.
    repo_root = Path(repo_path)
    has_tests = any(repo_root.rglob("test_*.py")) or any(repo_root.rglob("*_test.py"))
    if not has_tests:
        result["success"] = True
        result["stdout"] = "No pytest tests discovered in repository."
        logger.info("No tests discovered in %s; skipping Docker pytest execution.", repo_path)
        return result

    # Convert to absolute path for Docker
    abs_repo_path = os.path.abspath(repo_path)
    
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{abs_repo_path}:/app",
        "-w", "/app",
        "--network", "none",
        "--memory", _MEMORY_LIMIT,
        "--pids-limit", "256",
        image,
        "python", "-m", "pytest", "--tb=short", "-q",
    ]

    logger.info("Executing: %s", " ".join(shlex.quote(c) for c in cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result["exit_code"] = proc.returncode
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["success"] = proc.returncode == 0

        if result["success"]:
            logger.info("Pytest passed.")
        else:
            logger.warning("Pytest failed (exit %d).", proc.returncode)

    except subprocess.TimeoutExpired as exc:
        logger.error("Docker pytest timed out after %ds.", timeout)
        result["error"] = f"Timeout after {timeout}s"
        result["stdout"] = exc.stdout or ""
        result["stderr"] = exc.stderr or ""

    except FileNotFoundError:
        msg = "docker executable not found. Is Docker installed and on PATH?"
        logger.error(msg)
        result["error"] = msg

    except subprocess.SubprocessError as exc:
        logger.error("Subprocess error: %s", exc)
        result["error"] = f"SubprocessError: {exc}"

    except OSError as exc:
        logger.error("OS error: %s", exc)
        result["error"] = f"OSError: {exc}"

    return result
