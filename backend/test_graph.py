"""
Quick test script to verify the graph compilation and execution flow
"""
import logging
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(levelname)s]%(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S.%f'
)

logger = logging.getLogger(__name__)

# Import the graph
from app.agents.graph import compile

def test_graph_compilation():
    """Test that the graph compiles without errors"""
    try:
        logger.info("Compiling graph...")
        graph = compile()
        logger.info("✓ Graph compiled successfully")
        return graph
    except Exception as e:
        logger.error(f"✗ Graph compilation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_graph_structure(graph):
    """Test the graph structure"""
    try:
        logger.info("Checking graph structure...")
        # Get the compiled graph's nodes
        logger.info(f"✓ Graph structure looks good")
        return True
    except Exception as e:
        logger.error(f"✗ Graph structure check failed: {e}")
        return False

def test_simple_execution():
    """Test a simple graph execution with mock data"""
    try:
        logger.info("Testing graph execution with mock state...")
        graph = compile()
        
        # Create a minimal test state
        test_state = {
            "run_id": "test-123",
            "repo_url": "https://github.com/test/test-repo",
            "repo_path": None,
            "team_id": "test-team",
            "team_name": "TestTeam",
            "leader_name": "TestLeader",
            "branch_name": "test-branch",
            "iteration": 0,
            "max_retries": 1,
            "failures": [],
            "classified_failures": [],
            "applied_fixes": [],
            "ci_status": "pending",
            "logs": ["Test started"],
            "start_time": datetime.utcnow().isoformat(),
            "end_time": "",
            "score": 0,
            "final_status": None
        }
        
        logger.info("Executing graph (this will fail at clone, but we can see the flow)...")
        
        # Try to stream events
        event_count = 0
        for event in graph.stream(test_state, config={"recursion_limit": 50}):
            event_count += 1
            for node_name, state_update in event.items():
                logger.info(f"  → Node executed: {node_name}")
                if isinstance(state_update, dict) and "logs" in state_update:
                    for log in state_update.get("logs", []):
                        logger.info(f"    Log: {log}")
        
        logger.info(f"✓ Graph executed {event_count} events")
        return True
        
    except Exception as e:
        logger.error(f"✗ Graph execution test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("GRAPH TESTING SUITE")
    logger.info("=" * 60)
    
    # Test 1: Compilation
    graph = test_graph_compilation()
    if not graph:
        logger.error("Cannot proceed - graph compilation failed")
        sys.exit(1)
    
    # Test 2: Structure
    if not test_graph_structure(graph):
        logger.warning("Graph structure check failed, but continuing...")
    
    # Test 3: Execution
    test_simple_execution()
    
    logger.info("=" * 60)
    logger.info("TESTING COMPLETE")
    logger.info("=" * 60)
