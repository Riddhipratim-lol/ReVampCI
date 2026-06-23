"""
Git helper utility using GitPython.
Supports operations like clone, checkout branch, commit, push, and status check.
"""
import os
import re
import shutil
import git
from src.utils.logger import get_logger

logger = get_logger(__name__)

def validate_github_url(url: str) -> bool:
    """
    Validate if the string is a valid GitHub or general git repository URL.
    Supports HTTPS, SSH, and git protocols.
    """
    if not url:
        return False
    # Regex supporting common HTTPS, SSH, and Git protocols
    pattern = r"^(https?://|git@|git://)[a-zA-Z0-9.-]+[:/][a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+(\.git)?$"
    return bool(re.match(pattern, url))

def extract_repo_name(repo_url: str) -> str:
    """
    Extract the repository name from a git URL.
    Example: https://github.com/owner/repo.git -> repo
             git@github.com:owner/repo.git -> repo
    """
    url = repo_url
    if url.endswith(".git"):
        url = url[:-4]
    
    # Take the last path component
    parts = url.split("/")
    repo_name = parts[-1]
    
    # Handle SSH-style colon path separation
    if ":" in repo_name:
        repo_name = repo_name.split(":")[-1]
        
    return repo_name

def clone_repository(repo_url: str, dest_path: str) -> git.Repo:
    """
    Clones a git repository to the specified destination path.
    Cleans up any existing directory if present to guarantee a fresh clone.
    """
    logger.info(f"Preparing to clone repository: {repo_url} into {dest_path}")
    
    if os.path.exists(dest_path):
        logger.info(f"Target path {dest_path} already exists. Removing to perform a fresh clone.")
        try:
            shutil.rmtree(dest_path)
        except Exception as e:
            logger.error(f"Failed to remove existing directory {dest_path}: {e}")
            raise e
            
    os.makedirs(dest_path, exist_ok=True)
    
    try:
        repo = git.Repo.clone_from(repo_url, dest_path)
        logger.info(f"Successfully cloned repository: {repo_url}")
        return repo
    except Exception as e:
        logger.error(f"Failed to clone repository: {e}")
        if os.path.exists(dest_path):
            try:
                shutil.rmtree(dest_path)
            except Exception:
                pass
        raise e
