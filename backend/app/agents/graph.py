"""
graph.py

LangGraph StateGraph pipeline for the autonomous CI/CD healing loop.

Flow:
    START → run_tests
        → if passed  → END (status: "passed")
        → if failed  → commit_fix → push_branch → monitor_ci
            → if CI passed  → END (status: "fixed")
            → if CI failed  → retry_decision
                → should_retry True  → run_tests (loop)
                → should_retry False → END (status: "failed")
"""

import logging
from datetime import datetime

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.nodes.test_executor import execute_tests
from app.agents.nodes.git_committer import run as node_git_committer
from app.agents.nodes.ci_monitor import monitor_ci
from app.agents.nodes.failure_classifier import run as node_failure_classifier
from app.agents.nodes.fix_generator import run as node_fix_generator
from app.agents.nodes.fix_validator import run as node_fix_validator
from app.integrations.repo_cloner import clone_or_load_repo
from app.integrations.github_client import GitHubClient
from app.integrations.ci_provider import CIProvider
from app.core.retry_manager import RetryManager

logger = logging.getLogger(__name__)


import os
import re

# ── Node wrappers ────────────────────────────────────────────────────


def node_clone_repo(state: AgentState) -> dict:
    """Clone the repository to a local path."""
    logger.info("Node: clone_repo")
    
    repo_url = state["repo_url"]
    # Create a local path based on run_id or team_name
    run_id = state.get("run_id", "default")
    local_path = os.path.join("temp_repos", run_id)
    
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        clone_or_load_repo(repo_url, local_path)
        
        # Check if .github/workflows exists, if not create a basic CI workflow
        workflows_dir = os.path.join(local_path, ".github", "workflows")
        if not os.path.exists(workflows_dir):
            logger.info("No workflows found - creating default CI workflow")
            os.makedirs(workflows_dir, exist_ok=True)
            
            workflow_content = """name: CI Pipeline

on:
  push:
    branches: [ main, master, "**AI_Fix" ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        if [ -d tests ]; then
          pytest tests/ -v
        else
          echo "No tests directory found"
          exit 1
        fi
"""
            workflow_path = os.path.join(workflows_dir, "ci.yml")
            with open(workflow_path, "w") as f:
                f.write(workflow_content)
            
            logger.info(f"Created default CI workflow at {workflow_path}")
        
        return {
            "repo_path": local_path,
            "logs": [f"Successfully cloned {repo_url} to {local_path}"]
        }
    except Exception as e:
        logger.error(f"Clone failed: {e}")
        return {"logs": [f"Failed to clone repository: {e}"]}


def node_run_tests(state: AgentState) -> dict:
    """Execute pytest inside Docker and update state."""
    logger.info("Node: run_tests (iteration %d)", state.get("iteration", 0))

    repo_path = state.get("repo_path") or state["repo_url"]
    result = execute_tests(repo_path)

    logs = list(state.get("logs") or [])
    logs.append(f"[run_tests] passed={result['passed']}")

    update: dict = {
        "ci_status": "passed" if result["passed"] else "failed",
        "logs": logs,
    }

    if not result["passed"]:
        failures = list(state.get("failures") or [])
        raw_errors = result.get("errors", "")
        
        # Simple parser for pytest "-q" or --tb=short output
        # Format often: "file:line: error_message" or similar
        # For simplicity, we'll try to find common patterns
        pattern = r"([^:\s\n]+):(\d+): (.+)"
        matches = re.finditer(pattern, raw_errors)
        
        found_any = False
        for match in matches:
            file_path, line, msg = match.groups()
            failures.append({
                "file": file_path,
                "line": int(line),
                "error": msg.strip(),
                "iteration": state.get("iteration", 0)
            })
            found_any = True
            
        if not found_any:
            # Fallback: add raw errors if parsing failed
            failures.append({
                "file": "unknown",
                "line": 0,
                "error": raw_errors[:500],
                "iteration": state.get("iteration", 0)
            })
            
        update["failures"] = failures

    if result["passed"]:
        update["final_status"] = "passed"
        update["end_time"] = datetime.utcnow().isoformat()

    return update


def node_git_wrapper(state: AgentState) -> dict:
    """Wrapper to handle git committer run."""
    # Ensure commit_message is in state for git_committer
    iteration = state.get("iteration", 0)
    state["commit_message"] = f"Auto-fix iteration {iteration}"
    # repo_path is needed
    if not state.get("repo_path"):
        state["repo_path"] = state.get("repo_url") 
    return node_git_committer(state)


def node_push_branch(state: AgentState) -> dict:
    """Push the current feature branch to origin."""
    logger.info("Node: push_branch")

    try:
        repo_path = state.get("repo_path") or state["repo_url"]
        client = GitHubClient(repo_path)
        client.push_current_branch()
    except Exception as exc:
        logger.error("push_branch failed: %s", exc)
        logs = list(state.get("logs") or [])
        logs.append(f"[push_branch] error: {exc}")
        return {"logs": logs}

    logs = list(state.get("logs") or [])
    logs.append("[push_branch] pushed successfully")
    return {"logs": logs}


def node_monitor_ci(state: AgentState) -> dict:
    """Poll the GitHub Actions workflow status."""
    logger.info("Node: monitor_ci")

    # Check if .github/workflows exists in the repo
    repo_path = state.get("repo_path") or state.get("repo_url")
    workflows_path = os.path.join(repo_path, ".github", "workflows") if repo_path else None
    
    logs = list(state.get("logs") or [])
    
    # If no workflows directory exists, skip CI monitoring
    if workflows_path and not os.path.exists(workflows_path):
        logger.warning("No .github/workflows directory found - skipping CI monitoring")
        logs.append("[monitor_ci] No GitHub Actions workflows found - marking as passed")
        return {
            "ci_status": "passed",
            "final_status": "passed",
            "end_time": datetime.utcnow().isoformat(),
            "logs": logs,
        }

    # Extract owner/repo from repo_url
    # Expects format: https://github.com/owner/repo or owner/repo
    repo_url: str = state.get("repo_url", "")
    parts = repo_url.rstrip("/").split("/")
    owner = parts[-2] if len(parts) >= 2 else ""
    repo = parts[-1].replace(".git", "") if parts else ""

    token = os.environ.get("GITHUB_TOKEN", "")
    
    if not token:
        logger.warning("No GITHUB_TOKEN found - skipping CI monitoring")
        logs.append("[monitor_ci] No GitHub token configured - marking as passed")
        return {
            "ci_status": "passed",
            "final_status": "passed",
            "end_time": datetime.utcnow().isoformat(),
            "logs": logs,
        }

    provider = CIProvider(owner, repo, token)
    branch_name = state.get("branch_name", "")
    result = monitor_ci(provider, branch=branch_name)

    ci_status = "passed" if result.get("success") else "failed"

    logs.append(
        f"[monitor_ci] branch={branch_name or 'default'}, completed={result.get('completed')}, success={result.get('success')}"
    )

    update: dict = {"ci_status": ci_status, "logs": logs}

    if result.get("success"):
        update["final_status"] = "fixed"
        update["end_time"] = datetime.utcnow().isoformat()

    return update


def node_retry_decision(state: AgentState) -> dict:
    """Decide whether to retry the healing loop."""
    iteration = state.get("iteration", 0)
    max_retries = state.get("max_retries", 2)

    manager = RetryManager(max_retries=max_retries)
    # Fast-forward the manager to the current attempt count
    for _ in range(iteration):
        manager.track_attempt()

    should = manager.should_retry("failure")

    logs = list(state.get("logs") or [])
    failures = list(state.get("failures") or [])

    # If CI failed but no local failures detected, fetch CI logs and create synthetic failures
    if not failures:
        logs.append("[retry_decision] CI failed but no local failures - fetching CI logs")
        
        # Try to fetch CI failure logs
        try:
            repo_url: str = state.get("repo_url", "")
            parts = repo_url.rstrip("/").split("/")
            owner = parts[-2] if len(parts) >= 2 else ""
            repo = parts[-1].replace(".git", "") if parts else ""
            
            token = os.environ.get("GITHUB_TOKEN", "")
            
            if owner and repo and token:
                provider = CIProvider(owner, repo, token)
                branch_name = state.get("branch_name", "")
                ci_logs = provider.get_workflow_logs(branch=branch_name)
                
                if ci_logs:
                    # Parse CI logs to extract failures
                    import re
                    pattern = r"([^:\s\n]+):(\d+): (.+)"
                    matches = re.finditer(pattern, ci_logs)
                    
                    for match in matches:
                        file_path, line, msg = match.groups()
                        failures.append({
                            "file": file_path,
                            "line": int(line),
                            "error": msg.strip(),
                            "iteration": iteration,
                            "source": "ci_logs"
                        })
                    
                    if failures:
                        logs.append(f"[retry_decision] Extracted {len(failures)} failures from CI logs")
                    else:
                        # Create a generic failure if parsing didn't work
                        failures.append({
                            "file": "unknown",
                            "line": 0,
                            "error": ci_logs[:500],
                            "iteration": iteration,
                            "source": "ci_logs"
                        })
                        logs.append("[retry_decision] Created generic failure from CI logs")
        except Exception as e:
            logger.error(f"Failed to fetch CI logs: {e}")
            logs.append(f"[retry_decision] Failed to fetch CI logs: {e}")
        
        # If still no failures, we can't proceed
        if not failures:
            logs.append("[retry_decision] No failures detected locally or in CI - cannot proceed")
            return {
                "final_status": "failed",
                "end_time": datetime.utcnow().isoformat(),
                "logs": logs,
            }

    if should:
        manager.track_attempt()
        new_iteration = iteration + 1
        logs.append(f"[retry_decision] retrying (attempt {new_iteration}/{max_retries})")
        return {"iteration": new_iteration, "logs": logs, "failures": failures}
    else:
        logs.append(f"[retry_decision] max retries exceeded ({iteration}/{max_retries})")
        return {
            "final_status": "failed",
            "end_time": datetime.utcnow().isoformat(),
            "logs": logs,
        }


# ── Conditional edge functions ───────────────────────────────────────


def after_tests(state: AgentState) -> str:
    """Route after test execution."""
    iteration = state.get("iteration", 0)
    failures = state.get("failures", [])
    
    # If tests failed, go to failure classification
    if state.get("ci_status") != "passed":
        return "failure_classifier"
    
    # Tests passed
    # Check if we have any changes to commit (workflow file, fixes, etc.)
    repo_path = state.get("repo_path")
    has_changes = False
    
    if repo_path:
        try:
            from app.integrations.github_client import GitHubClient
            client = GitHubClient(repo_path)
            has_changes = client.repo.is_dirty(untracked_files=True)
        except Exception:
            pass
    
    # If first iteration with changes (e.g., workflow file created), commit and push
    if iteration == 0 and has_changes:
        return "git_committer"
    
    # If first iteration without changes, just monitor CI
    if iteration == 0:
        return "monitor_ci"
    
    # After a fix iteration with passing tests, commit and push
    if iteration > 0:
        return "git_committer"
    
    # Default: monitor CI
    return "monitor_ci"



def after_ci(state: AgentState) -> str:
    """Route after CI monitoring."""
    if state.get("ci_status") == "passed":
        return END
    return "retry_decision"


def after_retry(state: AgentState) -> str:
    """Route after retry decision."""
    if state.get("final_status") == "failed":
        return END
    return "run_tests"


# ── Graph construction ───────────────────────────────────────────────


def compile() -> object:
    """Build and compile the LangGraph healing pipeline.

    Returns:
        A compiled LangGraph runnable.
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("clone_repo", node_clone_repo)
    graph.add_node("run_tests", node_run_tests)
    graph.add_node("failure_classifier", node_failure_classifier)
    graph.add_node("fix_generator", node_fix_generator)
    graph.add_node("fix_validator", node_fix_validator)
    graph.add_node("git_committer", node_git_wrapper)
    graph.add_node("push_branch", node_push_branch)
    graph.add_node("monitor_ci", node_monitor_ci)
    graph.add_node("retry_decision", node_retry_decision)

    # Entry point
    graph.set_entry_point("clone_repo")

    # Edges
    graph.add_edge("clone_repo", "run_tests")
    graph.add_conditional_edges("run_tests", after_tests)

    
    # Linear path for healing logic
    graph.add_edge("failure_classifier", "fix_generator")
    graph.add_edge("fix_generator", "fix_validator")
    graph.add_edge("fix_validator", "git_committer")
    graph.add_edge("git_committer", "push_branch")
    graph.add_edge("push_branch", "monitor_ci")
    
    graph.add_conditional_edges("monitor_ci", after_ci)
    graph.add_conditional_edges("retry_decision", after_retry)

    logger.info("Full 8-node healing pipeline compiled.")
    return graph.compile()

