"""
test_executor.py

Agent node that delegates pytest execution to ``docker_sandbox``
and returns a normalised, structured result.
"""

import logging
from pathlib import Path

from app.core.docker_sandbox import run_pytest_in_docker

logger = logging.getLogger(__name__)


def collect_python_syntax_errors(repo_path: str) -> str:
    """Scan Python files for syntax errors and return pytest-style lines."""
    root = Path(repo_path)
    if not root.exists():
        return ""

    skip_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
    errors = []

    for py_file in root.rglob("*.py"):
        if any(part in skip_dirs for part in py_file.parts):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            compile(source, str(py_file), "exec")
        except SyntaxError as exc:
            rel = py_file.relative_to(root).as_posix()
            line_no = exc.lineno or 1
            msg = exc.msg or "invalid syntax"
            errors.append(f"{rel}:{line_no}: SyntaxError: {msg}")
        except Exception:
            # Ignore non-syntax file read/encode issues for now.
            continue

    return "\n".join(errors)


def execute_tests(repo_path: str) -> dict:
    """
    Run pytest against a repository and return a normalised result.

    Args:
        repo_path: Absolute path to the repository to test.

    Returns:
        A dict with keys:
            - passed (bool):  True if all tests passed.
            - logs (str):     Combined standard output from pytest.
            - errors (str):   Combined stderr and any error messages.
    """
    logger.info("Executing tests for repo: %s", repo_path)

    raw = run_pytest_in_docker(repo_path)

    passed = raw.get("success", False)
    logs = (raw.get("stdout") or "").strip()
    stderr = (raw.get("stderr") or "").strip()
    error = (raw.get("error") or "").strip()

    # Pytest usually reports failure locations in stdout, so include it for parsing.
    error_parts = [part for part in (logs, stderr, error) if part]
    errors = "\n".join(error_parts)

    if passed:
        logger.info("All tests passed.")
    else:
        logger.warning("Tests failed or encountered errors.")

    # If tests pass but source contains syntax errors, force a failed result so
    # the healing loop can still classify and attempt a fix.
    syntax_errors = collect_python_syntax_errors(repo_path)
    if passed and syntax_errors:
        passed = False
        errors = f"{errors}\n{syntax_errors}".strip()
        logger.warning("Syntax scan found issues despite passing tests.")

    return {
        "passed": passed,
        "logs": logs,
        "errors": errors,
    }


def run(state):
    """Execute tests and update state with results."""
    repo_path = state.get("repo_path", ".")
    
    result = execute_tests(repo_path)

    logs = list(state.get("logs") or [])

    state["passed"] = result["passed"]
    state["test_output"] = result["logs"]
    state["errors"] = result["errors"]
    state["test_errors"] = result["errors"]
    logs.append(f"Tests executed: {'passed' if result['passed'] else 'failed'}")
    state["logs"] = logs
    
    return state
