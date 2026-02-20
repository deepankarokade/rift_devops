"""
Production-ready FastAPI backend for DevOps AI Command Center
With WebSocket support for real-time pipeline updates
"""

import os
import asyncio
import json
import logging
import threading
from datetime import datetime
from uuid import uuid4
from typing import Optional, List, Dict, Any
from enum import Enum

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# LangGraph import
from app.agents.graph import compile as compile_graph

load_dotenv()

# Supabase imports
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL", "")
supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
supabase: Optional[Client] = None
if supabase_url and supabase_service_key:
    supabase = create_client(supabase_url, supabase_service_key)

app = FastAPI(title="DevOps AI Command Center API", version="1.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:3000", "http://localhost:8002", "http://localhost:8004", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Data Models ==============

class PipelineStatusEnum(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RunCreate(BaseModel):
    repo_url: str
    branch: Optional[str] = None
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    leader_name: Optional[str] = None


class RunResponse(BaseModel):
    id: str
    repo_url: str
    branch: str
    team_name: Optional[str] = None
    leader_name: Optional[str] = None
    status: str
    ci_status: str = "UNKNOWN"
    progress: float
    current_step: str
    total_failures: int
    total_fixes: int
    iterations_used: int
    score: float
    total_time_seconds: int
    created_at: datetime
    logs: List[str] = []


class PipelineUpdate(BaseModel):
    run_id: str
    status: str
    progress: float
    current_step: str
    iteration: int
    failures_detected: List[Dict[str, Any]] = []
    fixes_applied: List[Dict[str, Any]] = []
    logs: List[str] = []
    ci_status: str = "UNKNOWN"
    score: Optional[float] = None


# ============== In-Memory Storage ==============

# Pipeline runs storage (use Redis in production)
pipeline_runs: Dict[str, Dict[str, Any]] = {}
pipeline_logs: Dict[str, List[str]] = {}
websocket_connections: Dict[str, List[WebSocket]] = {}


def normalize_branch_segment(value: str) -> str:
    """Normalize a user-provided label for safe branch naming."""
    return "".join(ch if ch.isalnum() else "_" for ch in value.upper()).strip("_")


def create_branch_name(team_name: Optional[str], leader_name: Optional[str], fallback: Optional[str]) -> str:
    """Create branch name in TEAM_NAME_LEADER_AI_Fix format."""
    team = normalize_branch_segment(team_name or "")
    leader = normalize_branch_segment(leader_name or "")
    if team and leader:
        return f"{team}_{leader}_AI_Fix"
    if fallback:
        return fallback
    return "TEAM_LEADER_AI_Fix"


# ============== WebSocket Manager ==============

class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_update(self, update: Dict[str, Any]):
        """Send update to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(update)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_to_run(self, run_id: str, update: Dict[str, Any]):
        """Send update to specific run subscribers"""
        if run_id in websocket_connections:
            disconnected = []
            for connection in websocket_connections[run_id]:
                try:
                    await connection.send_json(update)
                except Exception:
                    disconnected.append(connection)
            
            for conn in disconnected:
                if conn in websocket_connections[run_id]:
                    websocket_connections[run_id].remove(conn)


manager = ConnectionManager()


# ============== WebSocket Endpoint ==============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time pipeline updates"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle client messages if needed
            message = json.loads(data)
            if message.get("type") == "subscribe":
                run_id = message.get("run_id")
                if run_id:
                    if run_id not in websocket_connections:
                        websocket_connections[run_id] = []
                    websocket_connections[run_id].append(websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        for run_id, conns in list(websocket_connections.items()):
            if websocket in conns:
                conns.remove(websocket)
            if not conns:
                websocket_connections.pop(run_id, None)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)
        for run_id, conns in list(websocket_connections.items()):
            if websocket in conns:
                conns.remove(websocket)
            if not conns:
                websocket_connections.pop(run_id, None)


# ============== API Endpoints ==============

@app.get("/")
async def root():
    return {"message": "DevOps AI Command Center API", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    """Check system health"""
    return {
        "status": "online",
        "timestamp": datetime.utcnow().isoformat(),
        "region": os.environ.get("NODE_REGION", "US-EAST-1")
    }


@app.get("/api/status", response_model=dict)
async def get_system_status():
    """Get current system status"""
    return {
        "status": "Autonomous Agent Active",
        "active_nodes": 142,
        "uptime": 99.99,
        "region": os.environ.get("NODE_REGION", "US-EAST-1")
    }


@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics"""
    # Calculate stats from pipeline runs
    total_runs = len(pipeline_runs)
    running_runs = sum(1 for r in pipeline_runs.values() if r.get("status") == "RUNNING")
    completed_runs = sum(1 for r in pipeline_runs.values() if r.get("status") == "COMPLETED")
    failed_runs = sum(1 for r in pipeline_runs.values() if r.get("status") == "FAILED")
    
    return {
        "active_deployments": running_runs,
        "ai_confidence": 98.4,
        "error_rate": 0.02,
        "infra_cost": 2450,
        "success_rate": (completed_runs / total_runs * 100) if total_runs > 0 else 100,
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "failed_runs": failed_runs
    }


@app.post("/api/runs", response_model=RunResponse)
async def create_run(run_data: RunCreate, background_tasks: BackgroundTasks):
    """Create a new pipeline run"""
    run_id = str(uuid4())
    created_at = datetime.utcnow()
    branch_name = create_branch_name(run_data.team_name, run_data.leader_name, run_data.branch)
    
    # Initialize run
    pipeline_runs[run_id] = {
        "id": run_id,
        "repo_url": run_data.repo_url,
        "branch": branch_name,
        "team_id": run_data.team_id,
        "team_name": run_data.team_name,
        "leader_name": run_data.leader_name,
        "status": "PENDING",
        "ci_status": "UNKNOWN",
        "progress": 0,
        "current_step": "Initializing pipeline...",
        "iteration": 0,
        "total_failures": 0,
        "total_fixes": 0,
        "iterations_used": 0,
        "score": 0.0,
        "total_time_seconds": 0,
        "created_at": created_at,
        "failures_detected": [],
        "fixes_applied": [],
    }
    pipeline_logs[run_id] = []
    
    # Add initial log
    log_msg = f"[{created_at.isoformat()}] Pipeline initialized for {run_data.repo_url}"
    pipeline_logs[run_id].append(log_msg)
    
    # Start pipeline in background
    background_tasks.add_task(run_pipeline, run_id, run_data.repo_url, branch_name)
    
    return RunResponse(
        id=run_id,
        repo_url=run_data.repo_url,
        branch=branch_name,
        team_name=run_data.team_name,
        leader_name=run_data.leader_name,
        status="PENDING",
        ci_status="UNKNOWN",
        progress=0,
        current_step="Initializing pipeline...",
        total_failures=0,
        total_fixes=0,
        iterations_used=0,
        score=0.0,
        total_time_seconds=0,
        created_at=created_at,
        logs=pipeline_logs[run_id]
    )


@app.get("/api/runs", response_model=List[RunResponse])
async def get_runs(limit: int = 20):
    """Get all pipeline runs"""
    runs = list(pipeline_runs.values())
    runs.sort(key=lambda x: x["created_at"], reverse=True)
    
    return [
        RunResponse(
            id=run["id"],
            repo_url=run["repo_url"],
            branch=run["branch"],
            team_name=run.get("team_name"),
            leader_name=run.get("leader_name"),
            status=run["status"],
            ci_status=run.get("ci_status", "UNKNOWN"),
            progress=run["progress"],
            current_step=run["current_step"],
            total_failures=run["total_failures"],
            total_fixes=run["total_fixes"],
            iterations_used=run["iterations_used"],
            score=run["score"],
            total_time_seconds=run["total_time_seconds"],
            created_at=run["created_at"],
            logs=pipeline_logs.get(run["id"], [])[-10:]
        )
        for run in runs[:limit]
    ]


@app.get("/api/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str):
    """Get a specific run by ID"""
    if run_id not in pipeline_runs:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run = pipeline_runs[run_id]
    return RunResponse(
        id=run["id"],
        repo_url=run["repo_url"],
        branch=run["branch"],
        team_name=run.get("team_name"),
        leader_name=run.get("leader_name"),
        status=run["status"],
        ci_status=run.get("ci_status", "UNKNOWN"),
        progress=run["progress"],
        current_step=run["current_step"],
        total_failures=run["total_failures"],
        total_fixes=run["total_fixes"],
        iterations_used=run["iterations_used"],
        score=run["score"],
        total_time_seconds=run["total_time_seconds"],
        created_at=run["created_at"],
        logs=pipeline_logs.get(run_id, [])
    )


@app.get("/api/runs/{run_id}/status")
async def get_pipeline_status(run_id: str):
    """Get pipeline status and logs"""
    if run_id not in pipeline_runs:
        return {
            "run_id": run_id,
            "status": "UNKNOWN",
            "progress": 0,
            "current_step": "No pipeline found",
            "logs": []
        }
    
    run = pipeline_runs[run_id]
    return {
        "run_id": run_id,
        "status": run["status"],
        "ci_status": run.get("ci_status", "UNKNOWN"),
        "progress": run["progress"],
        "current_step": run["current_step"],
        "iteration": run.get("iteration", 0),
        "failures_detected": run.get("failures_detected", []),
        "fixes_applied": run.get("fixes_applied", []),
        "logs": pipeline_logs.get(run_id, [])
    }


# ============== Background Pipeline Execution ==============

async def run_pipeline(run_id: str, repo_url: str, branch: str):
    """Execute the CI/CD healing pipeline using real LangGraph execution"""
    start_time = datetime.utcnow()
    
    try:
        # Update status to RUNNING
        pipeline_runs[run_id]["status"] = "RUNNING"
        
        # Compile and run the real graph
        try:
            graph = compile_graph()
        except Exception as e:
            logger.error(f"Failed to compile graph: {e}")
            pipeline_runs[run_id]["status"] = "FAILED"
            pipeline_runs[run_id]["current_step"] = f"Graph compilation failed: {str(e)}"
            return
        
        # Provide complete initial state with all required fields
        initial_state = {
            "run_id": run_id,
            "repo_url": repo_url,
            "repo_path": None,
            "team_id": pipeline_runs[run_id].get("team_id") or "default",
            "team_name": pipeline_runs[run_id].get("team_name") or "default_team",
            "leader_name": pipeline_runs[run_id].get("leader_name") or "admin",
            "branch_name": branch,
            "iteration": 0,
            "max_retries": 3,
            "failures": [],
            "classified_failures": [],
            "applied_fixes": [],
            "ci_status": "pending",
            "logs": [f"Pipeline started for {repo_url} on branch {branch}"],
            "start_time": datetime.utcnow().isoformat(),
            "end_time": "",
            "score": 0,
            "final_status": None
        }
        
        # Mapping graph nodes to user-friendly steps with real progress percentages
        node_map = {
            "clone_repo": ("Cloning repository to local sandbox...", 5),
            "run_tests": ("Executing Dockerized tests...", 20),
            "failure_classifier": ("AI diagnosing test failures...", 35),
            "fix_generator": ("AI generating code fixes...", 50),
            "fix_validator": ("Performing AST syntax validation...", 60),
            "git_committer": ("AI committing verified fixes...", 70),
            "push_branch": ("Pushing fix to remote...", 80),
            "monitor_ci": ("Polling CI/CD status...", 90),
            "retry_decision": ("Deciding on next steps...", 95),
            "repo_analyzer": ("Analyzing repository structure...", 5),
            "test_discovery": ("Discovering test files...", 10),
            "test_executor": ("Executing tests...", 30),
            "reflection_agent": ("Reflecting on the fix...", 85),
        }

        # Stream execution. The healing graph can legitimately run more than
        # 25 steps when retries are enabled, so raise the recursion limit.
        recursion_limit = max(100, (initial_state["max_retries"] + 1) * 20)
        merged_state = dict(initial_state)
        async for event in graph.astream(
            initial_state,
            config={"recursion_limit": recursion_limit},
        ):
            # event is a dict mapping node_name -> state_update
            for node_name, state_update in event.items():
                step_info = node_map.get(node_name, (f"Processing: {node_name}...", 50))
                if isinstance(state_update, dict):
                    merged_state.update(state_update)
                else:
                    # Handle non-dict state updates (e.g., final result)
                    state_update = {"result": str(state_update)}
                
                # Update global run state
                pipeline_runs[run_id]["current_step"] = step_info[0]
                pipeline_runs[run_id]["progress"] = step_info[1]
                
                # Safely get iteration from state_update
                iteration_val = None
                if isinstance(state_update, dict):
                    iteration_val = state_update.get("iteration")
                if iteration_val is not None:
                    pipeline_runs[run_id]["iteration"] = iteration_val
                
                # Merge logs
                new_logs = []
                if isinstance(state_update, dict):
                    new_logs = state_update.get("logs", [])
                for log in new_logs:
                    if log not in pipeline_logs[run_id]:
                        pipeline_logs[run_id].append(f"[{datetime.utcnow().isoformat()}] {log}")
                
                # Merge failures/fixes if present in ANY node's state (using latest available)
                if isinstance(state_update, dict):
                    if "failures" in state_update:
                        pipeline_runs[run_id]["failures_detected"] = state_update["failures"]
                        pipeline_runs[run_id]["total_failures"] = len(state_update["failures"])
                    
                    if "applied_fixes" in state_update:
                        pipeline_runs[run_id]["fixes_applied"] = state_update["applied_fixes"]
                        pipeline_runs[run_id]["total_fixes"] = len(state_update["applied_fixes"])

                    if "ci_status" in state_update:
                        pipeline_runs[run_id]["ci_status"] = str(state_update["ci_status"]).upper()

                # Send WebSocket update
                update = {
                    "type": "pipeline_update",
                    "run_id": run_id,
                    "status": "RUNNING",
                    "ci_status": pipeline_runs[run_id].get("ci_status", "UNKNOWN"),
                    "progress": step_info[1],
                    "current_step": step_info[0],
                    "iteration": state_update.get("iteration", pipeline_runs[run_id].get("iteration", 0)),
                    "failures_detected": pipeline_runs[run_id].get("failures_detected", []),
                    "fixes_applied": pipeline_runs[run_id].get("fixes_applied", []),
                    "logs": pipeline_logs.get(run_id, [])[-5:]
                }
                await manager.send_to_run(run_id, update)

        # Final terminal state check without re-running the graph
        final_state = merged_state
        total_time = int((datetime.utcnow() - start_time).total_seconds())
        
        status = "COMPLETED"
        final_msg = "Pipeline completed successfully"
        final_status = final_state.get("final_status")
        if not final_status:
            ci_status_value = str(final_state.get("ci_status", "")).lower()
            final_status = "passed" if ci_status_value == "passed" else "failed"
        final_score = 100.0 if final_status in ["passed", "fixed"] else 0.0
        
        if final_status == "failed":
            status = "FAILED"
            final_msg = "Max retries exceeded without fix"
        
        # Update final run record
        pipeline_runs[run_id].update({
            "status": status,
            "progress": 100,
            "current_step": final_msg,
            "iterations_used": final_state.get("iteration", 1),
            "score": final_score,
            "total_time_seconds": total_time,
            "ci_status": final_state.get("ci_status", "UNKNOWN").upper()
        })
        
        # Send final update
        await manager.send_to_run(run_id, {
            "type": "pipeline_complete",
            "run_id": run_id,
            "status": status,
            "progress": 100,
            "current_step": final_msg,
            "score": final_score,
            "total_time_seconds": total_time,
            "total_failures": pipeline_runs[run_id].get("total_failures", 0),
            "total_fixes": pipeline_runs[run_id].get("total_fixes", 0),
            "iterations_used": final_state.get("iteration", 1),
            "ci_status": pipeline_runs[run_id].get("ci_status"),
            "logs": pipeline_logs.get(run_id, [])
        })
        
        
    except Exception as e:
        # Handle errors
        error_msg = f"Pipeline failed: {str(e)}"
        pipeline_runs[run_id]["status"] = "FAILED"
        pipeline_runs[run_id]["current_step"] = error_msg
        
        if run_id in pipeline_logs:
            pipeline_logs[run_id].append(f"[{datetime.utcnow().isoformat()}] ERROR: {error_msg}")
        
        # Send error update
        await manager.send_to_run(run_id, {
            "type": "pipeline_error",
            "run_id": run_id,
            "status": "FAILED",
            "error": error_msg
        })


@app.get("/api/actions")
async def get_recent_actions():
    """Get recent AI agent actions"""
    # Get recent runs for actions
    runs = sorted(pipeline_runs.values(), key=lambda x: x["created_at"], reverse=True)[:10]
    
    actions = []
    for run in runs:
        if run["status"] == "COMPLETED":
            action_type = "Auto-healed"
            status = "success"
        elif run["status"] == "FAILED":
            action_type = "Analysis Failed"
            status = "error"
        elif run["status"] == "RUNNING":
            action_type = "Running Pipeline"
            status = "running"
        else:
            action_type = "Pending"
            status = "pending"
        
        actions.append({
            "id": run["id"],
            "type": action_type,
            "description": f"Repository: {run['repo_url']} - {run.get('total_failures', 0)} failures, {run.get('total_fixes', 0)} fixes",
            "timestamp": run["created_at"].isoformat() if isinstance(run["created_at"], datetime) else run["created_at"],
            "status": status
        })
    
    # Add default demo actions if no runs
    if not actions:
        actions = [
            {"id": "1", "type": "Kubernetes Auto-scaled", "description": "Traffic spike detected in US-West cluster. Provisioned 4 additional nodes.", "timestamp": datetime.utcnow().isoformat(), "status": "success"},
            {"id": "2", "type": "Security Vulnerability Patched", "description": "Identified CVE-2024-5120 in base image.", "timestamp": datetime.utcnow().isoformat(), "status": "success"},
            {"id": "3", "type": "Node Health Remediation", "description": "Node i-0a2f1b unresponsive. Restarted successfully.", "timestamp": datetime.utcnow().isoformat(), "status": "success"}
        ]
    
    return actions


@app.get("/api/latency")
async def get_latency_stats():
    """Get latency distribution stats"""
    return {
        "regions": [
            {"name": "US-EAST-1", "latency": 12, "percentage": 85},
            {"name": "EU-WEST-1", "latency": 42, "percentage": 45},
            {"name": "AP-SOUTH-1", "latency": 68, "percentage": 30}
        ]
    }


# ============== Supabase Auth Endpoints ==============

@app.get("/api/user/profile")
async def get_user_profile():
    """Get user profile from Supabase"""
    if not supabase:
        return {"error": "Supabase not configured"}
    
    try:
        user = supabase.auth.get_user()
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        return {
            "id": user.user.id,
            "email": user.user.email,
            "created_at": user.user.created_at
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    import socket

    # Force port 8002
    port = 8002
    
    # Check if port 8002 is in use
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            in_use = s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        in_use = False

    if in_use:
        print(f"ERROR: Port {port} is already in use!")
        print(f"Please stop the process using port {port} and try again.")
        import sys
        sys.exit(1)

    print(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

# Export for Vercel
handler = app
