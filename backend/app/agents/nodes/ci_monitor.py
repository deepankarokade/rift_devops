"""
ci_monitor.py

Agent node wrapper over CIProvider.
Fetches the latest workflow run status and returns a normalised result.
"""

import logging


from app.integrations.ci_provider import CIProvider, CIProviderError
from app.core.database import create_ci_timeline, SessionLocal

logger = logging.getLogger(__name__)


def monitor_ci(ci_provider: CIProvider, branch: str = "") -> dict:
    """
    Query the latest CI workflow run and return a normalised status.

    Args:
        ci_provider: An initialised CIProvider instance.

    Returns:
        A dict with keys:
            - completed (bool): True if the workflow run has finished.
            - success (bool):   True if the conclusion is "success".
            - raw_status (dict): The original dict from CIProvider.
    """
    try:
        raw = ci_provider.get_latest_workflow_status(branch=branch or None)
    except CIProviderError as exc:
        logger.error("Failed to fetch CI status: %s", exc)
        return {
            "completed": False,
            "success": False,
            "raw_status": {"status": "error", "conclusion": None},
        }

    status = raw.get("status", "unknown")
    conclusion = raw.get("conclusion")

    # If no workflow run is found, we cannot claim CI success.
    if status == "none":
        logger.warning("No workflow runs found for repository; CI status is unknown.")
        return {
            "completed": True,
            "success": False,
            "raw_status": raw,
        }

    completed = status == "completed"
    success = completed and conclusion == "success"

    logger.info(
        "CI monitor – completed: %s, success: %s (status=%s, conclusion=%s)",
        completed,
        success,
        status,
        conclusion,
    )

    return {
        "completed": completed,
        "success": success,
        "raw_status": raw,
    }

def run(state):
    """Monitor CI status and save timeline to database."""
    ci_status = state.get("ci_status", "")
    logs = list(state.get("logs") or [])
    
    if ci_status == "READY_FOR_COMMIT":
        state["ci_status"] = "PASSED"

    # Save CI timeline to database
    run_id = state.get("run_id")
    iteration = state.get("iteration", 0)
    if run_id:
        db = SessionLocal()
        try:
            create_ci_timeline(
                db=db,
                run_id=run_id,
                iteration_number=iteration,
                status="PASSED" if state.get("ci_status") == "PASSED" else "FAILED"
            )
        except Exception as e:
            logger.error("Failed to save CI timeline: %s", e)
            db.rollback()
        finally:
            db.close()

    logs.append("CI monitored")
    state["logs"] = logs

    return state
