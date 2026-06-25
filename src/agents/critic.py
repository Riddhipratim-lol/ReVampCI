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

from src.utils.architecture_critic import (
    detect_circular_dependencies,
    detect_large_classes,
    detect_high_complexity_modules,
    detect_architectural_violations,
    calculate_maintainability_score
)

class PriorityRankingItem(BaseModel):
    task: str = Field(description="The refactoring task description.")
    priority: str = Field(description="Priority level: HIGH, MEDIUM, or LOW.")
    effort: str = Field(description="Estimated effort to fix: HIGH, MEDIUM, or LOW.")
    impact: str = Field(description="Description of the architectural impact of fixing this issue.")
    file: str = Field(description="Target file name or path.")

# output schema for critic agent
class CriticOutputSchema(BaseModel):
    """Structured output from the Critic Agent."""
    identified_issues: List[str] = Field(
        description="List of code issues, technical debt, style violations, or code smells identified in the repository."
    )
    refactoring_tasks: List[str] = Field(
        description="Structured, actionable list of tasks for the refactoring agent, detailing what needs to be changed."
    )
    priority_rankings: List[PriorityRankingItem] = Field(
        description="Prioritized rankings for the refactoring tasks."
    )
    maintainability_score: int = Field(
        description="Overall architectural maintainability score of the codebase from 0 to 100."
    )

def critic_node(state: GraphState) -> Dict[str, Any]:
    """
    Analyzes the parsed repository structure and file contents in the graph state
    to identify code quality and technical debt issues, returning identified issues,
    a prioritized list of refactoring tasks, priority rankings, and maintainability score.
    """
    logger.info("critic_node running")
    
    file_contents = state.get("file_contents", {})
    repo_structure = state.get("repository_structure", {})
    ast_data = state.get("ast_data", {})
    dependency_graph = state.get("dependency_graph", {})
    
    if not file_contents:
        logger.info("No file contents found in state to analyze. Returning empty list.")
        return {
            "identified_issues": [],
            "refactoring_tasks": [],
            "priority_rankings": [],
            "maintainability_score": 100
        }

    # 1. Run Programmatic Architecture Critic Analysis
    cycles = detect_circular_dependencies(dependency_graph)
    violations = detect_architectural_violations(dependency_graph)
    large_classes = detect_large_classes(ast_data)
    complex_modules = detect_high_complexity_modules(ast_data)
    baseline_score = calculate_maintainability_score(
        cycles=cycles,
        violations=violations,
        large_classes=large_classes,
        complex_modules=complex_modules
    )

    logger.info(f"Programmatic Analysis: {len(cycles)} cycles, {len(violations)} violations, "
                f"{len(large_classes)} large classes, {len(complex_modules)} complex modules. "
                f"Baseline Score: {baseline_score}")

    # Format the file contents for the LLM to inspect
    formatted_files = []
    for filepath, content in file_contents.items():
        formatted_files.append(f"--- File: {filepath} ---\n{content}\n")
    
    files_context = "\n".join(formatted_files)
    structure_context = f"Directory Structure:\n{repo_structure}"

    # Format programmatic analysis metrics
    prog_cycles_str = "\n".join([f"- Cycle: " + " -> ".join(c) for c in cycles]) if cycles else "None detected"
    prog_violations_str = "\n".join([f"- {v['description']}" for v in violations]) if violations else "None detected"
    prog_large_classes_str = "\n".join([f"- Class '{c['class_name']}' in {c['file']} ({c['lines']} lines, {c['methods_count']} methods)" for c in large_classes]) if large_classes else "None detected"
    prog_complex_str = "\n".join([f"- {c['file']} ({c['total_functions']} functions/methods)" for c in complex_modules]) if complex_modules else "None detected"

    # Build the prompt
    system_prompt = (
        "You are a senior software architect and expert code reviewer.\n"
        "Your task is to analyze the source code of the repository and perform a comprehensive architecture critic:\n"
        "- Assess overall technical debt and code smells.\n"
        "- Identify architectural boundary violations and circular dependencies.\n"
        "- Identify large classes or overly complex modules.\n"
        "- Generate a final maintainability score from 0 (completely unmaintainable) to 100 (excellent architecture).\n"
        "- Generate a structured, actionable plan of prioritized refactoring tasks to improve the codebase. "
        "For each task, assign priority (HIGH/MEDIUM/LOW), estimated effort (HIGH/MEDIUM/LOW), target file, and expected impact."
    )

    user_content = (
        f"Please analyze the following repository structure, file contents, and programmatic architectural analysis:\n\n"
        f"{structure_context}\n\n"
        f"Programmatic Analysis Results:\n"
        f"1. Circular Dependencies:\n{prog_cycles_str}\n"
        f"2. Architectural Layer Violations:\n{prog_violations_str}\n"
        f"3. Large Classes:\n{prog_large_classes_str}\n"
        f"4. High Complexity Modules:\n{prog_complex_str}\n"
        f"5. Programmatic Maintainability Baseline Score: {baseline_score}/100\n\n"
        f"Source Files:\n"
        f"{files_context}\n\n"
        f"Identify all issues, provide a list of concrete refactoring tasks, rank them by priority/effort/impact, and assign a final maintainability score."
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
        
        logger.info(f"Critic identified {len(result.identified_issues)} issues and {len(result.refactoring_tasks)} tasks. Final Maintainability Score: {result.maintainability_score}")
        
        # Convert PriorityRankingItem objects to dicts for GraphState compatibility
        serialized_rankings = []
        for ranking in result.priority_rankings:
            serialized_rankings.append({
                "task": ranking.task,
                "priority": ranking.priority,
                "effort": ranking.effort,
                "impact": ranking.impact,
                "file": ranking.file
            })

        return {
            "identified_issues": result.identified_issues,
            "refactoring_tasks": result.refactoring_tasks,
            "priority_rankings": serialized_rankings,
            "maintainability_score": result.maintainability_score
        }
    except Exception as e:
        logger.error(f"Error in critic_node during LLM invocation: {e}")
        # Return fallback values to ensure the graph does not crash
        return {
            "identified_issues": [f"Error during critic analysis: {str(e)}"],
            "refactoring_tasks": [],
            "priority_rankings": [],
            "maintainability_score": baseline_score
        }
