from typing import TypedDict, List, Optional
from datetime import datetime

class AgentState(TypedDict):
    # Database identifiers
    team_id: str
    run_id: str
    
    # Repository info
    repo_url: str
    repo_path: Optional[str]
    team_name: str
    leader_name: str
    branch_name: str
    
    # Pipeline state
    iteration: int
    max_retries: int
    failures: List[dict]
    classified_failures: List[str]
    applied_fixes: List[str]
    ci_status: str
    logs: List[str]
    
    # Timing
    start_time: str
    end_time: str
    
    # Results
    score: int
    final_status: Optional[str]
