"""
LangGraph compilation, routing, and workflow setup.
Compiles the Repository Setup and Parser nodes into a stateful graph.
"""
from langgraph.graph import StateGraph, START, END
from src.state import GraphState
from src.agents.codespace import setup_codespace
from src.agents.parser import parse_repository

# Initialize StateGraph with our GraphState TypedDict
workflow = StateGraph(GraphState)

# Add nodes for setup and parser
workflow.add_node("setup_codespace", setup_codespace)
workflow.add_node("parse_repository", parse_repository)

# Set up edges
workflow.add_edge(START, "setup_codespace")
workflow.add_edge("setup_codespace", "parse_repository")
workflow.add_edge("parse_repository", END)

# Compile graph into an executable application
app = workflow.compile()
