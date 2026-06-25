"""
Analysis Agent node implementation.
Parses files to generate AST data, global symbol table, and internal dependency graph.
"""
from typing import Dict, Any
from src.state import GraphState
from src.utils.logger import get_logger
from src.utils.ast_parser import analyze_repo_deeply

logger = get_logger(__name__)

def analysis_agent(state: GraphState) -> Dict[str, Any]:
    """
    Reads file contents and repository structure from state,
    analyzes AST, extracts symbols, builds dependency graph,
    and returns updated state keys: ast_data, symbol_table, dependency_graph.
    """
    logger.info("analysis_agent running")
    
    repo_path = state.get("repo_path")
    file_contents = state.get("file_contents", {})
    repo_structure = state.get("repository_structure", {})
    
    if not repo_path:
        error_msg = "No repo_path provided in the graph state."
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    files = repo_structure.get("files", [])
    
    if not files or not file_contents:
        logger.info("No files or contents found to analyze. Returning empty structures.")
        return {
            "ast_data": {},
            "symbol_table": {},
            "dependency_graph": {}
        }
        
    try:
        results = analyze_repo_deeply(repo_path, files, file_contents)
        
        return {
            "ast_data": results["ast_data"],
            "symbol_table": results["symbol_table"],
            "dependency_graph": results["dependency_graph"]
        }
    except Exception as e:
        logger.error(f"Error in analysis_agent during deep code analysis: {e}")
        # Return fallback values to ensure the graph does not crash
        return {
            "ast_data": {},
            "symbol_table": {},
            "dependency_graph": {}
        }
