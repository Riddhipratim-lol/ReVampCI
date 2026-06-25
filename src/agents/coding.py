"""
Coding Agent node implementation.
Modifies code, applies refactoring operations, and attempts to resolve
compiler/tester issues fed back from the Tester Agent.
"""
import os
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from src.state import GraphState
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

class RefactoredFile(BaseModel):
    """Details of a single refactored file."""
    filepath: str = Field(
        description="The relative filepath of the modified file (must match a path in the scanned files)."
    )
    new_content: str = Field(
        description="The complete new content of the file, replacing the old content entirely. Do not truncate the content."
    )
    change_description: str = Field(
        description="A brief description of what was refactored in this file."
    )

class RefactorOutputSchema(BaseModel):
    """Structured output from the Refactoring Agent."""
    modified_files: List[RefactoredFile] = Field(
        description="List of files that were modified during the refactoring process."
    )

def refactoring_node(state: GraphState) -> Dict[str, Any]:
    """
    Reads the refactoring tasks and file contents from the state,
    invokes Gemini 3.1 Flash Lite to refactor the code according to the tasks,
    saves the modified files to disk, and updates modified_files and execution_history in the state.
    """
    logger.info("refactoring_node running")
    
    repo_path = state.get("repo_path")
    file_contents = state.get("file_contents", {})
    refactoring_tasks = state.get("refactoring_tasks", [])
    
    if not repo_path:
        error_msg = "No repo_path provided in the graph state."
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    if not file_contents:
        logger.info("No file contents found in state to refactor. Skipping node.")
        return {
            "modified_files": [],
            "execution_history": state.get("execution_history", [])
        }
        
    if not refactoring_tasks:
        logger.info("No refactoring tasks provided. Skipping node.")
        return {
            "modified_files": [],
            "execution_history": state.get("execution_history", [])
        }

    # Format files context and tasks context for the LLM
    formatted_files = []
    for filepath, content in file_contents.items():
        formatted_files.append(f"--- File: {filepath} ---\n{content}\n")
    files_context = "\n".join(formatted_files)
    
    # creates vertical markdown bullet points
    tasks_context = "\n".join([f"- {task}" for task in refactoring_tasks])

    system_prompt = (
        "You are an expert software developer responsible for refactoring a repository.\n"
        "You are given a list of files and their contents, along with a list of refactoring tasks to execute.\n"
        "For each file that needs modifications to address one or more tasks:\n"
        "1. Apply the refactoring changes cleanly.\n"
        "2. Ensure you preserve all existing functionality and external behavior (do not break the code).\n"
        "3. Output the relative filepath, the complete new content of the file, and a description of changes.\n"
        "4. Do not make unnecessary changes to files not related to the refactoring tasks."
    )

    user_content = (
        f"Refactoring Tasks:\n{tasks_context}\n\n"
        f"Source Files:\n{files_context}\n\n"
        f"Please apply the refactoring and output the modified files."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    try:
        # Initialize Gemini 3.1 Flash Lite as configured in settings
        model = init_chat_model(
            settings.REFACTOR_MODEL,
            model_provider="google_genai"
        ).with_structured_output(RefactorOutputSchema)
        
        logger.info(f"Invoking model {settings.REFACTOR_MODEL} with structured output")
        result = model.invoke(messages)
        
        modified_paths = []
        execution_history = list(state.get("execution_history", []))
        
        logger.info(f"Refactor agent returned {len(result.modified_files)} modified files")
        
        for modified_file in result.modified_files:
            filepath = modified_file.filepath
            new_content = modified_file.new_content
            change_desc = modified_file.change_description
            
            full_path = os.path.join(repo_path, filepath)
            
            # Ensure the directory exists (in case a new file was created, or nesting structure)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Write the new content to disk
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)
                
            logger.info(f"Saved refactored file: {filepath}")
            modified_paths.append(filepath)
            
            # Record execution trace
            execution_history.append({
                "node": "refactoring_agent",
                "action": "refactor_file",
                "file": filepath,
                "description": change_desc
            })
            
        return {
            "modified_files": modified_paths,
            "execution_history": execution_history
        }
    except Exception as e:
        logger.error(f"Error in refactoring_node during LLM invocation: {e}")
        return {
            "modified_files": [],
            "execution_history": state.get("execution_history", []) + [{
                "node": "refactoring_agent",
                "action": "error",
                "description": f"Refactoring failed with error: {str(e)}"
            }]
        }
