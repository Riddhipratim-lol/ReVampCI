"""
Report Agent node implementation.
Gathers all execution history, modified files, identified issues, and test results,
and generates a structured markdown final report summarizing the refactoring session.
"""
from typing import Dict, Any
from langchain.chat_models import init_chat_model
from src.state import GraphState
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

def report_node(state: GraphState) -> Dict[str, Any]:
    """
    Generates a comprehensive markdown report summarizing the refactoring process,
    using an LLM to generate an executive summary.
    """
    logger.info("report_node running")
    
    identified_issues = state.get("identified_issues", [])
    refactoring_tasks = state.get("refactoring_tasks", [])
    modified_files = state.get("modified_files", [])
    test_results = state.get("test_results", {})
    execution_history = state.get("execution_history", [])
    
    # Phase 2 intelligence state
    languages = state.get("languages", [])
    frameworks = state.get("frameworks", [])
    dependencies = state.get("dependencies", [])
    project_metadata = state.get("project_metadata", {})
    
    # 1. Ask LLM to generate a professional Executive Summary
    system_prompt = (
        "You are an expert software architect and technical writer.\n"
        "Your task is to write a concise, professional Executive Summary for an autonomous code refactoring run.\n"
        "Summarize the goal of the refactoring, what changes were made, and the outcome of the verification tests.\n"
        "Keep the summary concise (1-2 paragraphs) and professional. Do not use markdown headers inside your response."
    )
    
    # Extract file-level changes from execution history for context
    change_details = []
    for trace in execution_history:
        if trace.get("action") == "refactor_file":
            change_details.append(f"- {trace.get('file')}: {trace.get('description')}")
            
    test_summary = test_results.get("summary", "No tests run.")
    test_success = test_results.get("success", True)
    
    user_content = (
        f"Issues Identified:\n" + "\n".join([f"- {issue}" for issue in identified_issues]) + "\n\n"
        f"Tasks Planned:\n" + "\n".join([f"- {task}" for task in refactoring_tasks]) + "\n\n"
        f"Modified Files & Actions:\n" + "\n".join(change_details) + "\n\n"
        f"Test Results: {'PASS' if test_success else 'FAIL'} - {test_summary}\n\n"
        f"Please write a short Executive Summary summarizing the accomplishments and state of the repository."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    try:
        model = init_chat_model(
            settings.REFACTOR_MODEL,
            model_provider="google_genai"
        )
        logger.info(f"Invoking model {settings.REFACTOR_MODEL} to generate executive summary")
        response = model.invoke(messages)
        content = response.content
        if isinstance(content, str):
            exec_summary = content.strip()
        elif isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    parts.append(part["text"])
                elif hasattr(part, "text"):
                    parts.append(part.text)
            exec_summary = "".join(parts).strip()
        else:
            exec_summary = str(content).strip()
    except Exception as e:
        logger.error(f"Error generating executive summary with LLM: {e}")
        exec_summary = (
            f"Autonomous refactoring session completed. A total of {len(modified_files)} files were refactored "
            f"to address code quality and technical debt. Verification tests yielded: {test_summary}."
        )

    # 2. Programmatically format the final report in Markdown
    languages_str = ", ".join(languages) if languages else "None detected"
    frameworks_str = ", ".join(frameworks) if frameworks else "None detected"
    build_systems_str = ", ".join(project_metadata.get("build_systems", [])) if project_metadata.get("build_systems") else "None detected"
    entry_points_str = ", ".join(project_metadata.get("entry_points", [])) if project_metadata.get("entry_points") else "None detected"
    
    priority_rankings = state.get("priority_rankings", [])
    maintainability_score = state.get("maintainability_score")

    report_lines = [
        "# ReVampCI Refactoring Report",
        "",
        "## Executive Summary",
        exec_summary,
        "",
        "## Repository Profile",
        f"- **Languages**: {languages_str}",
        f"- **Primary Language**: `{project_metadata.get('primary_language', 'Unknown')}`",
        f"- **Frameworks / Libraries**: {frameworks_str}",
        f"- **Build Systems**: {build_systems_str}",
        f"- **Entry Points**: {entry_points_str}",
        f"- **Total Files**: {project_metadata.get('total_files', 0)} ({project_metadata.get('total_directories', 0)} directories)",
        f"- **Lines of Code (LOC)**: {project_metadata.get('total_loc', 0)}",
        f"- **Dependencies**: {len(dependencies)} packages detected",
    ]
    
    if maintainability_score is not None:
        report_lines.append(f"- **Architectural Maintainability Score**: `{maintainability_score}/100`")
        
    report_lines.extend([
        "",
        "## 1. Identified Issues",
    ])
    
    if identified_issues:
        for issue in identified_issues:
            report_lines.append(f"- {issue}")
    else:
        report_lines.append("No issues identified.")
        
    report_lines.extend([
        "",
        "## 2. Priority Refactoring Plan",
    ])
    
    if priority_rankings:
        for ranking in priority_rankings:
            task = ranking.get("task", "")
            priority = ranking.get("priority", "")
            effort = ranking.get("effort", "")
            impact = ranking.get("impact", "")
            file = ranking.get("file", "")
            report_lines.append(
                f"- **Task**: {task}\n"
                f"  - **Target File**: `{file}`\n"
                f"  - **Priority**: `{priority}` | **Effort**: `{effort}`\n"
                f"  - **Expected Architectural Impact**: {impact}"
            )
    elif refactoring_tasks:
        for task in refactoring_tasks:
            report_lines.append(f"- {task}")
    else:
        report_lines.append("No refactoring tasks planned.")
        
    report_lines.extend([
        "",
        "## 3. Modified Files & Changes",
    ])
    
    if change_details:
        report_lines.extend(change_details)
    else:
        report_lines.append("No files were modified.")
        
    report_lines.extend([
        "",
        "## 4. Verification Results",
        f"- **Testing Framework**: `{test_results.get('framework', 'unknown')}`",
        f"- **Outcome**: {'✅ PASS' if test_success else '❌ FAIL'}",
        f"- **Details**: {test_summary}",
    ])
    
    failures = test_results.get("failures", [])
    if failures:
        report_lines.extend([
            "",
            "### Test Failures",
        ])
        for fail in failures:
            report_lines.append(f"- {fail}")
            
    final_report = "\n".join(report_lines)
    logger.info("Report generation complete.")
    
    # Record report action in execution history
    updated_history = list(execution_history)
    updated_history.append({
        "node": "report_agent",
        "action": "generate_report",
        "description": "Final refactoring report generated."
    })
    
    return {
        "final_report": final_report,
        "execution_history": updated_history
    }
