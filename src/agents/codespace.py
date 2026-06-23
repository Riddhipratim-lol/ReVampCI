"""
Codespace Agent node implementation.
Handles cloning the repository, checking out working branch, installing dependencies,
and setting up the execution environment inside GitHub Codespaces.
"""
import os
from typing import Dict, Any
from src.state import GraphState
from src.utils.git_helper import validate_github_url, extract_repo_name, clone_repository
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

def setup_codespace(state: GraphState) -> Dict[str, Any]:
    """
    Validates the repo_url from the state, extracts the repository name,
    clones it to the workspace_clones/ directory, and stores the repo_path in the state.
    """
    repo_url = state.get("repo_url")
    logger.info(f"setup_codespace running for URL: {repo_url}")
    
    if not repo_url:
        error_msg = "No repo_url provided in the graph state."
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    if not validate_github_url(repo_url):
        error_msg = f"Invalid git repository URL provided: {repo_url}"
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    repo_name = extract_repo_name(repo_url)
    dest_path = os.path.join(settings.CLONES_DIR, repo_name)
    
    try:
        clone_repository(repo_url, dest_path)
    except Exception as e:
        error_msg = f"Failed to clone repository during setup: {e}"
        logger.error(error_msg)
        raise e
        
    logger.info(f"Repository setup complete. Stored repo_path: {dest_path}")
    return {
        "repo_path": dest_path
    }
