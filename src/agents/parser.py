"""
Parser Agent node implementation.
Traverses repository files, reads text source code,
and maps out dependencies and project structures.
"""
import os
from typing import Dict, Any, List
from src.state import GraphState
from src.utils.logger import get_logger
from src.utils.repository_intelligence import analyze_repository

logger = get_logger(__name__)

def is_binary_file(filepath: str) -> bool:
    """
    Check if a file is binary by looking at its first 1024 bytes for null characters.
    If it finds a null byte (\x00), it's a telling indicator that the file is binary (like an image, .pyc, or .exe) rather than plain text.
    Handles exceptions by assuming the file could be binary.
    """
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            return b'\x00' in chunk
    except Exception as e:
        logger.warning(f"Error checking if {filepath} is binary: {e}. Assuming binary.")
        return True

def parse_repository(state: GraphState) -> Dict[str, Any]:
    """
    Traverses the repository path in state["repo_path"],
    reads all text source files, filters out binaries and typical build/dependency
    directories, and updates the graph state with structure and contents.
    """
    repo_path = state.get("repo_path")
    logger.info(f"parse_repository running for path: {repo_path}")
    
    if not repo_path:
        error_msg = "No repo_path provided in the graph state."
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    if not os.path.exists(repo_path):
        error_msg = f"Repository path does not exist: {repo_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    # Standard ignore lists
    ignore_dirs = {
        ".git", "node_modules", "venv", ".venv", "__pycache__", 
        ".pytest_cache", ".egg-info", "build", "dist", ".idea", ".vscode"
    }
    ignore_files = {".DS_Store", "uv.lock", "poetry.lock", "package-lock.json"}
    
    file_contents: Dict[str, str] = {}
    structure_files: List[str] = []
    structure_dirs: List[str] = []
    
    for root, dirs, files in os.walk(repo_path):
        # Modify dirs in-place to prevent traversing ignored subdirectories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for d in dirs:
            full_dir_path = os.path.join(root, d)
            rel_dir_path = os.path.relpath(full_dir_path, repo_path)
            structure_dirs.append(rel_dir_path)
            
        for f in files:
            if f in ignore_files:
                continue
                
            full_file_path = os.path.join(root, f)
            rel_file_path = os.path.relpath(full_file_path, repo_path)
            
            # Skip binary files
            if is_binary_file(full_file_path):
                logger.debug(f"Ignoring binary file: {rel_file_path}")
                continue
                
            try:
                # It explicitly uses utf-8 and passes errors='replace'. This guarantees that if it encounters an unusual character, it won't crash; it will simply substitute it with a placeholder character (``) and keep moving.
                with open(full_file_path, 'r', encoding='utf-8', errors='replace') as file_obj:
                    content = file_obj.read()
                    file_contents[rel_file_path] = content
                    structure_files.append(rel_file_path)
            except Exception as e:
                logger.warning(f"Failed to read file {rel_file_path}: {e}")
                
    repository_structure = {
        "files": structure_files,
        "directories": structure_dirs
    }
    
    logger.info(f"Repository parsing complete. Scanned {len(structure_files)} files.")
    
    # Run repository intelligence analysis (Phase 2)
    intelligence = analyze_repository(repo_path, file_contents, repository_structure)
    
    return {
        "file_contents": file_contents,
        "repository_structure": repository_structure,
        "languages": intelligence["languages"],
        "frameworks": intelligence["frameworks"],
        "dependencies": intelligence["dependencies"],
        "project_metadata": intelligence["project_metadata"]
    }
