"""
Critic Agent node implementation.
Analyzes code for technical debt, architecture problems, maintainability, complexity,
and outputs a prioritized plan of refactoring tasks.
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from src.state import GraphState
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# output schema for critic agent
class CriticOutputSchema(BaseModel):
    """Structured output from the Critic Agent."""
    identified_issues: List[str] = Field(
        description="List of code issues, technical debt, style violations, or code smells identified in the repository."
    )
    refactoring_tasks: List[str] = Field(
        description="Structured, actionable list of tasks for the refactoring agent, detailing what needs to be changed."
    )

def critic_node(state: GraphState) -> Dict[str, Any]:
    """
    Analyzes the parsed repository structure and file contents in the graph state
    to identify code quality and technical debt issues, returning identified issues
    and a prioritized list of refactoring tasks.
    """
    logger.info("critic_node running")
    
    file_contents = state.get("file_contents", {})
    repo_structure = state.get("repository_structure", {})
    
    if not file_contents:
        logger.info("No file contents found in state to analyze. Returning empty list.")
        return {
            "identified_issues": [],
            "refactoring_tasks": []
        }

    # Format the file contents for the LLM to inspect
    formatted_files = []
    for filepath, content in file_contents.items():
        formatted_files.append(f"--- File: {filepath} ---\n{content}\n")
    
    files_context = "\n".join(formatted_files)
    structure_context = f"Directory Structure:\n{repo_structure}"

    # Build the prompt
    system_prompt = (
        "You are a senior software architect and expert code reviewer.\n"
        "Your task is to analyze the source code of the repository and identify:\n"
        "- Dead code / Unused imports / Unused variables\n"
        "- Code smells / Poor coding practices\n"
        "- Duplicate logic / Redundant helper functions\n"
        "- Long functions or files / High complexity modules\n"
        "- Style violations or naming issues\n\n"
        "Generate a structured, actionable plan of refactoring tasks to improve the codebase. "
        "Each task should be clear enough for a developer (or coding agent) to implement directly."
    )

    user_content = (
        f"Please analyze the following repository structure and file contents:\n\n"
        f"{structure_context}\n\n"
        f"Source Files:\n"
        f"{files_context}\n\n"
        f"Identify all issues and provide a list of concrete refactoring tasks."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    try:
        # Initialize Gemini 3.5 Flash as configured in settings
        model = init_chat_model(
            settings.CRITIC_MODEL,
            model_provider="google_genai"
        ).with_structured_output(CriticOutputSchema)
        
        logger.info(f"Invoking model {settings.CRITIC_MODEL} with structured output")
        result = model.invoke(messages)
        
        logger.info(f"Critic identified {len(result.identified_issues)} issues and {len(result.refactoring_tasks)} tasks")
        
        return {
            "identified_issues": result.identified_issues,
            "refactoring_tasks": result.refactoring_tasks
        }
    except Exception as e:
        logger.error(f"Error in critic_node during LLM invocation: {e}")
        # Return fallback values to ensure the graph does not crash
        return {
            "identified_issues": [f"Error during critic analysis: {str(e)}"],
            "refactoring_tasks": []
        }
