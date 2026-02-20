from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes import (
    repo_analyzer,
    test_discovery,
    test_executor,
    failure_classifier,
    fix_generator,
    fix_validator,
    git_committer,
    ci_monitor,
    reflection_agent
)

def build_graph():

    graph = StateGraph(AgentState)

    graph.add_node("repo_analyzer", repo_analyzer.run)
    graph.add_node("test_discovery", test_discovery.run)
    graph.add_node("test_executor", test_executor.run)
    graph.add_node("failure_classifier", failure_classifier.run)
    graph.add_node("fix_generator", fix_generator.run)
    graph.add_node("fix_validator", fix_validator.run)
    graph.add_node("git_committer", git_committer.run)
    graph.add_node("ci_monitor", ci_monitor.run)
    graph.add_node("reflection_agent", reflection_agent.run)

    graph.set_entry_point("repo_analyzer")

    graph.add_edge("repo_analyzer", "test_discovery")
    graph.add_edge("test_discovery", "test_executor")
    graph.add_edge("test_executor", "failure_classifier")
    graph.add_edge("failure_classifier", "fix_generator")
    graph.add_edge("fix_generator", "fix_validator")

    def decide(state):

        if state["ci_status"] == "PASSED":
            return END

        if state["iteration"] >= state["max_retries"]:
            return END

        return "reflection_agent"

    graph.add_conditional_edges("fix_validator", decide)

    graph.add_edge("reflection_agent", "test_executor")

    return graph.compile()
