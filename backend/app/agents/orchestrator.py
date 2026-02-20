from datetime import datetime
from app.agents.graph_builder import build_graph
from app.core.result_writer import save_results
from app.core.database import create_run, update_run_status, create_ci_timeline, SessionLocal

def run_pipeline(state):
    """Run the CI/CD healing pipeline."""
    state["start_time"] = datetime.utcnow().isoformat()

    # Create database session
    db = SessionLocal()
    try:
        # Create a new run in the database
        run = create_run(
            db=db,
            team_id=state.get("team_id"),
            repo_url=state.get("repo_url", ""),
            status="RUNNING"
        )
        state["run_id"] = str(run.id)
    except Exception as e:
        print(f"Failed to create run in database: {e}")
        db.rollback()
    finally:
        db.close()

    graph = build_graph()

    final_state = graph.invoke(state)

    final_state["end_time"] = datetime.utcnow().isoformat()

    # Calculate total time
    total_time = (
        datetime.fromisoformat(final_state["end_time"]) -
        datetime.fromisoformat(final_state["start_time"])
    ).total_seconds()

    # Update run in database
    db = SessionLocal()
    try:
        if "run_id" in final_state:
            update_run_status(
                db=db,
                run_id=final_state["run_id"],
                status="PASSED" if final_state.get("ci_status") == "PASSED" else "FAILED",
                total_failures=len(final_state.get("failures", [])),
                total_fixes=len(final_state.get("applied_fixes", [])),
                iterations_used=final_state.get("iteration", 0),
                total_time_seconds=int(total_time)
            )
    except Exception as e:
        print(f"Failed to update run in database: {e}")
        db.rollback()
    finally:
        db.close()

    final_state = save_results(final_state)

    return final_state
