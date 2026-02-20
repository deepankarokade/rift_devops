"""
guard.py

Validation utilities for branch names, commit messages, and retry limits.
"""

import re


def generate_branch(team: str, leader: str) -> str:
    """
    Generate a branch name based on team and leader.
    
    Args:
        team: The team name.
        leader: The leader name.
    
    Returns:
        A formatted branch name.
    """
    team_clean = re.sub(r'[^a-zA-Z0-9]', '-', team.lower())
    leader_clean = re.sub(r'[^a-zA-Z0-9]', '-', leader.lower())
    return f"fix/{team_clean}-{leader_clean}"


def validate_branch(team: str, leader: str, branch: str) -> None:
    """
    Validate that the branch matches the expected format for the team/leader.
    
    Args:
        team: The team name.
        leader: The leader name.
        branch: The branch name to validate.
    
    Raises:
        Exception: If the branch format is invalid.
    """
    expected_branch = generate_branch(team, leader)
    if branch != expected_branch:
        raise Exception(f"Invalid branch format. Expected: {expected_branch}")


def validate_commit_message(message: str) -> None:
    """
    Validate that the commit message has the required prefix.
    
    Args:
        message: The commit message to validate.
    
    Raises:
        Exception: If the commit message format is invalid.
    """
    if not message.startswith("[AI-AGENT]"):
        raise Exception("Invalid commit message: must start with [AI-AGENT]")


def validate_retry(iteration: int, max_retries: int) -> None:
    """
    Validate that the retry limit has not been exceeded.
    
    Args:
        iteration: The current iteration number.
        max_retries: The maximum number of retries allowed.
    
    Raises:
        Exception: If the retry limit has been exceeded.
    """
    if iteration > max_retries:
        raise Exception("Retry limit exceeded")
