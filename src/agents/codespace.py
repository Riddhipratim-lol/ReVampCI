"""
Codespace Agent node implementation.
Handles cloning the repository, checking out working branch, installing dependencies,
and setting up the execution environment inside GitHub Codespaces.
"""
import os
import sys
import subprocess
from typing import Dict, Any
from src.state import GraphState
from src.utils.git_helper import validate_github_url, extract_repo_name, clone_repository
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

def prepare_environment(repo_path: str) -> None:
    """
    Detects build/dependency files in the cloned repository and prepares the
    execution environment by installing required dependencies.
    """
    logger.info(f"Preparing execution environment in {repo_path}")
    
    # 1. Python dependencies
    requirements_path = os.path.join(repo_path, "requirements.txt")
    pyproject_path = os.path.join(repo_path, "pyproject.toml")
    setup_py_path = os.path.join(repo_path, "setup.py")
    
    if os.path.exists(requirements_path):
        logger.info("Found requirements.txt. Installing Python dependencies...")
        try:
            subprocess.run(["uv", "pip", "install", "-r", "requirements.txt"], cwd=repo_path, capture_output=True, text=True, check=True)
            logger.info("Successfully installed requirements using uv.")
        except Exception:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=repo_path, capture_output=True, text=True, check=True)
                logger.info("Successfully installed requirements using pip.")
            except Exception as e:
                logger.error(f"Failed to install Python dependencies via pip: {e}")
                
    elif os.path.exists(pyproject_path) or os.path.exists(setup_py_path):
        logger.info("Found pyproject.toml or setup.py. Installing Python package...")
        try:
            subprocess.run(["uv", "pip", "install", "-e", "."], cwd=repo_path, capture_output=True, text=True, check=True)
            logger.info("Successfully installed package in editable mode using uv.")
        except Exception:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], cwd=repo_path, capture_output=True, text=True, check=True)
                logger.info("Successfully installed package in editable mode using pip.")
            except Exception as e:
                logger.error(f"Failed to install Python package via pip: {e}")

    # 2. Node.js dependencies
    package_json_path = os.path.join(repo_path, "package.json")
    if os.path.exists(package_json_path):
        logger.info("Found package.json. Installing Node dependencies...")
        try:
            subprocess.run(["npm", "install"], cwd=repo_path, capture_output=True, text=True, check=True)
            logger.info("Successfully installed Node dependencies.")
        except Exception as e:
            logger.error(f"Failed to install Node dependencies: {e}")

    # 3. Go dependencies
    go_mod_path = os.path.join(repo_path, "go.mod")
    if os.path.exists(go_mod_path):
        logger.info("Found go.mod. Fetching Go dependencies...")
        try:
            subprocess.run(["go", "mod", "download"], cwd=repo_path, capture_output=True, text=True, check=True)
            logger.info("Successfully prepared Go dependencies.")
        except Exception as e:
            logger.error(f"Failed to prepare Go dependencies: {e}")

def setup_codespace(state: GraphState) -> Dict[str, Any]:
    """
    Validates the repo_url from the state, extracts the repository name,
    clones it to the workspace_clones/ directory, prepares the execution
    environment, and stores repo_path and workspace_path in the state.
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
        
    try:
        prepare_environment(dest_path)
    except Exception as e:
        logger.warning(f"Error preparing execution environment: {e}")
        
    logger.info(f"Repository setup complete. Stored repo_path: {dest_path}")
    return {
        "repo_path": dest_path,
        "workspace_path": settings.WORKSPACE_ROOT
    }

""" 
Graph State
    │
    ▼
setup_codespace()
    │
    ├── Validate GitHub URL
    │
    ├── Extract repo name
    │
    ├── Clone repository
    │
    ├── Prepare environment
    │       ├── Python deps
    │       ├── Node deps
    │       └── Go deps
    │
    └── Return repo/workspace paths
"""