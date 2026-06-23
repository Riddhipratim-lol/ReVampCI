"""
LangGraph compilation, routing, and workflow setup.
Compiles the Repository Setup and Parser nodes into a stateful graph.
"""
from langgraph.graph import StateGraph, START, END
from src.state import GraphState
from src.agents.codespace import setup_codespace
from src.agents.parser import parse_repository
from src.agents.critic import critic_node
from src.agents.coding import refactoring_node

# Initialize StateGraph with our GraphState TypedDict
workflow = StateGraph(GraphState)

# Add nodes
workflow.add_node("setup_codespace", setup_codespace)
workflow.add_node("parse_repository", parse_repository)
workflow.add_node("critic_node", critic_node)
workflow.add_node("refactoring_node", refactoring_node)

# Set up edges
workflow.add_edge(START, "setup_codespace")
workflow.add_edge("setup_codespace", "parse_repository")
workflow.add_edge("parse_repository", "critic_node")
workflow.add_edge("critic_node", "refactoring_node")
workflow.add_edge("refactoring_node", END)

# Compile graph into an executable application
app = workflow.compile()
