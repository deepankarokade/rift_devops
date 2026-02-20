import json
import os
from datetime import datetime
from app.core.scoring_engine import calculate_score
from app.core.database import update_run_status, SessionLocal

RESULT_PATH = os.path.join(os.path.dirname(__file__), "..", "results", "results.json")

def save_results(state):
    """Save results to JSON file and update database."""
    total_time = (
        datetime.fromisoformat(state["end_time"]) -
        datetime.fromisoformat(state["start_time"])
    ).total_seconds()

    commit_count = state.get("commit_count", 0)
    score = calculate_score(total_time, commit_count)

    result = {
        "repository": state.get("repo_url", ""),
        "branch": state.get("branch_name", ""),
        "failures_detected": len(state.get("failures", [])),
        "fixes_applied": len(state.get("applied_fixes", [])),
        "iterations": state.get("iteration", 0),
        "final_status": state.get("ci_status", ""),
        "time_taken": f"{int(total_time)} seconds",
        "score": score
    }

    # Ensure directory exists
    os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)

    with open(RESULT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    # Update run in database with final results
    run_id = state.get("run_id")
    if run_id:
        db = SessionLocal()
        try:
            update_run_status(
                db=db,
                run_id=run_id,
                status=state.get("ci_status", "FAILED"),
                total_failures=len(state.get("failures", [])),
                total_fixes=len(state.get("applied_fixes", [])),
                iterations_used=state.get("iteration", 0),
                total_time_seconds=int(total_time)
            )
        except Exception as e:
            print(f"Failed to update run in database: {e}")
            db.rollback()
        finally:
            db.close()

    state["score"] = score
    return state
