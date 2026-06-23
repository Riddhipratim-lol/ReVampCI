"""
LangGraph State definition for the multi-agent refactoring workflow.
"""
from typing import TypedDict, List, Dict, Any

class GraphState(TypedDict):
    # Repository details
    repo_url: str
    repo_path: str
    
    # Scanned repository files and structures
    repository_structure: Dict[str, Any]
    file_contents: Dict[str, str]
    
    # Critic identified issues and task list
    identified_issues: List[str]
    refactoring_tasks: List[str]
    
    # Coding agent outputs
    modified_files: List[str]
    
    # Testing outputs
    test_results: Dict[str, Any]
    build_logs: str
    
    # Trace of executed steps
    execution_history: List[Dict[str, Any]]
    
    # Final generated report
    final_report: str
