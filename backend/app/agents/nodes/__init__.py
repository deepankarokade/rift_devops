"""
nodes/__init__.py

Agent nodes for the CI/CD pipeline healing system.
"""

from app.agents.nodes.ci_monitor import monitor_ci, run as ci_monitor_run
from app.agents.nodes.failure_classifier import classify_failure
from app.agents.nodes.fix_generator import generate_fix
from app.agents.nodes.fix_validator import validate_fix
from app.agents.nodes.git_committer import run as git_committer_run
from app.agents.nodes.repo_analyser import run as repo_analyzer
from app.agents.nodes.test_discovery import run as test_discovery
from app.agents.nodes.test_executor import execute_tests, run as test_executor_run
from app.agents.nodes.relection_agent import reflect

# Aliases for graph_builder compatibility
repo_analyzer = repo_analyzer
test_discovery = test_discovery
test_executor = test_executor_run
failure_classifier = type('FailureClassifier', (), {'run': classify_failure})()
fix_generator = type('FixGenerator', (), {'run': generate_fix})()
fix_validator = type('FixValidator', (), {'run': validate_fix})()
git_committer = type('GitCommitter', (), {'run': git_committer_run})()
ci_monitor = ci_monitor_run
reflection_agent = type('ReflectionAgent', (), {'run': reflect})()

__all__ = [
    "repo_analyzer",
    "test_discovery",
    "test_executor",
    "failure_classifier",
    "fix_generator",
    "fix_validator",
    "git_committer",
    "ci_monitor",
    "reflection_agent",
    "monitor_ci",
    "classify_failure",
    "generate_fix",
    "validate_fix",
    "commit_fix",
    "execute_tests",
    "reflect",
]
