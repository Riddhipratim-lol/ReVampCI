"""
Repair Agent node implementation.
Analyzes test and build failure logs to identify root causes,
generates corrected file contents, writes them to disk,
and updates the LangGraph state.
"""
import os
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from src.state import GraphState
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

class RepairedFile(BaseModel):
    """Details of a single repaired file."""
    filepath: str = Field(
        description="The relative filepath of the modified file (must match a path in the scanned files)."
    )
    new_content: str = Field(
        description="The complete new content of the file, replacing the old content entirely. Do not truncate the content."
    )
    change_description: str = Field(
        description="A brief description of what was corrected in this file."
    )

class RepairOutputSchema(BaseModel):
    """Structured output from the Repair Agent."""
    repaired_files: List[RepairedFile] = Field(
        description="List of files that were modified to repair the test or build failures."
    )
    explanation: str = Field(
        description="A summary explanation of the root cause identified and how it was fixed."
    )

def repair_node(state: GraphState) -> Dict[str, Any]:
    """
    Analyzes the test failure / build logs from the state,
    invokes Gemini 3.1 Flash Lite to generate fixes,
    writes updated files to disk, and updates repair stats in the state.
    """
    logger.info("repair_node running")
    
    repo_path = state.get("repo_path")
    file_contents = dict(state.get("file_contents", {}))
    test_results = state.get("test_results", {})
    build_logs = state.get("build_logs", "")
    repair_attempts = state.get("repair_attempts", 0)
    repair_history = list(state.get("repair_history", []))
    modified_files = list(state.get("modified_files", []))
    execution_history = list(state.get("execution_history", []))
    
    if not repo_path:
        error_msg = "No repo_path provided in the graph state."
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    if not file_contents:
        logger.warning("No file contents found in state to repair. Skipping node.")
        return {}

    # Format the file contexts for the LLM
    formatted_files = []
    for filepath, content in file_contents.items():
        formatted_files.append(f"--- File: {filepath} ---\n{content}\n")
    files_context = "\n".join(formatted_files)

    # Format specific test failures
    failures_list = test_results.get("failures", [])
    failures_context = "\n".join([f"- {f}" for f in failures_list]) if failures_list else "None listed specifically."

    # Prompt constructing
    system_prompt = (
        "You are an expert software developer and debugging assistant.\n"
        "You are given a list of repository files along with the logs and failure messages from a failed test/build run.\n"
        "Your task is to:\n"
        "1. Analyze the build logs, stdout/stderr, and traceback details to identify the root cause of the failure.\n"
        "2. Produce code modifications (repairs) to resolve the build/compilation errors or failing assertions.\n"
        "3. Output the relative filepath, the complete new content of the file, and a description of changes.\n"
        "4. Ensure you preserve all other existing functionality (do not break unrelated features).\n"
        "5. Keep modifications scoped to the files that need fixing."
    )

    user_content = (
        f"Failed Build/Test Logs:\n{build_logs}\n\n"
        f"Specific Failures:\n{failures_context}\n\n"
        f"Source Files:\n{files_context}\n\n"
        f"Please analyze these errors and repair the codebase."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    new_attempts = repair_attempts + 1

    try:
        # Initialize Gemini model as configured
        model = init_chat_model(
            settings.REFACTOR_MODEL,
            model_provider="google_genai"
        ).with_structured_output(RepairOutputSchema)
        
        logger.info(f"Invoking repair model {settings.REFACTOR_MODEL} for attempt {new_attempts}")
        result = model.invoke(messages)
        
        logger.info(f"Repair agent returned {len(result.repaired_files)} repaired files. Explanation: {result.explanation}")
        
        repaired_paths = []
        for repaired_file in result.repaired_files:
            filepath = repaired_file.filepath
            new_content = repaired_file.new_content
            change_desc = repaired_file.change_description
            
            full_path = os.path.join(repo_path, filepath)
            
            # Ensure folder exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Save corrected file to disk
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)
                
            # Update state's file_contents
            file_contents[filepath] = new_content
            
            logger.info(f"Saved repaired file to disk and state: {filepath}")
            
            # Track as modified file if not already tracked
            if filepath not in modified_files:
                modified_files.append(filepath)
            repaired_paths.append(filepath)
            
            # Add to execution history
            execution_history.append({
                "node": "repair_agent",
                "action": "repair_file",
                "file": filepath,
                "description": change_desc,
                "attempt": new_attempts
            })
            
        repair_entry = {
            "attempt": new_attempts,
            "explanation": result.explanation,
            "repaired_files": repaired_paths
        }
        repair_history.append(repair_entry)
        
        execution_history.append({
            "node": "repair_agent",
            "action": "repair_summary",
            "attempt": new_attempts,
            "description": f"Repair completed: {result.explanation}"
        })
        
        return {
            "repair_attempts": new_attempts,
            "repair_history": repair_history,
            "file_contents": file_contents,
            "modified_files": modified_files,
            "execution_history": execution_history,
            "error_logs": build_logs  # Save current build logs as error logs in state
        }
        
    except Exception as e:
        logger.error(f"Error in repair_node during LLM invocation: {e}")
        error_entry = {
            "attempt": new_attempts,
            "explanation": f"Failed with exception: {str(e)}",
            "repaired_files": []
        }
        repair_history.append(error_entry)
        execution_history.append({
            "node": "repair_agent",
            "action": "error",
            "attempt": new_attempts,
            "description": f"Repair failed with error: {str(e)}"
        })
        return {
            "repair_attempts": new_attempts,
            "repair_history": repair_history,
            "execution_history": execution_history,
            "error_logs": f"{build_logs}\n\n[Repair Agent Exception]: {str(e)}"
        }
