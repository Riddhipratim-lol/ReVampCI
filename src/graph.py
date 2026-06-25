"""
LangGraph compilation, routing, and workflow setup.
Compiles the Repository Setup and Parser nodes into a stateful graph.
"""
from langgraph.graph import StateGraph, START, END
from src.state import GraphState
from src.agents.codespace import setup_codespace
from src.agents.parser import parse_repository
from src.agents.analysis import analysis_agent
from src.agents.critic import critic_node
from src.agents.coding import refactoring_node
from src.agents.tester import tester_node
from src.agents.repair import repair_node
from src.agents.report import report_node

# Initialize StateGraph with our GraphState TypedDict
workflow = StateGraph(GraphState)

# Add nodes
workflow.add_node("setup_codespace", setup_codespace)
workflow.add_node("parse_repository", parse_repository)
workflow.add_node("analysis_agent", analysis_agent)
workflow.add_node("critic_node", critic_node)
workflow.add_node("refactoring_node", refactoring_node)
workflow.add_node("tester_node", tester_node)
workflow.add_node("repair_node", repair_node)
workflow.add_node("report_node", report_node)

# Routing function for conditional validation loop
def should_continue(state: GraphState) -> str:
    test_results = state.get("test_results", {})
    attempts = state.get("repair_attempts", 0)
    
    # If all tests passed, proceed to report
    if test_results.get("success", True):
        return "report_node"
        
    # If tests failed but we reached max retries (3 attempts), proceed to report
    if attempts >= 3:
        return "report_node"
        
    # Otherwise, go to repair node
    return "repair_node"

# Set up edges
workflow.add_edge(START, "setup_codespace")
workflow.add_edge("setup_codespace", "parse_repository")
workflow.add_edge("parse_repository", "analysis_agent")
workflow.add_edge("analysis_agent", "critic_node")
workflow.add_edge("critic_node", "refactoring_node")
workflow.add_edge("refactoring_node", "tester_node")

# Conditional validation loop routing
workflow.add_conditional_edges(
    "tester_node",
    should_continue,
    {
        "repair_node": "repair_node",
        "report_node": "report_node"
    }
)

workflow.add_edge("repair_node", "tester_node")
workflow.add_edge("report_node", END)

# Compile graph into an executable application
app = workflow.compile()
