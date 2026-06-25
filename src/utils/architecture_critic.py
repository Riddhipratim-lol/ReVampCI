"""
Programmatic architecture critic utilities.
Analyzes AST data and dependency graphs to identify architectural smells, layering violations, and cycles.
"""
from typing import Dict, Any, List, Set

def detect_circular_dependencies(dependency_graph: Dict[str, List[str]]) -> List[List[str]]:
    """
    DFS-based cycle detection algorithm to identify dependency cycles in the repository.
    Returns a list of cycles, where each cycle is represented as a list of file paths.
    """
    cycles: List[List[str]] = []
    # 0 = unvisited, 1 = visiting (on current recursion stack), 2 = fully visited
    visited: Dict[str, int] = {node: 0 for node in dependency_graph}

    def dfs(node: str, path: List[str], path_set: Set[str]):
        visited[node] = 1
        path.append(node)
        path_set.add(node)

        for neighbor in dependency_graph.get(node, []):
            if neighbor not in visited:
                # If neighbor is not in the graph nodes, treat it as unvisited/leaf
                continue
            if visited[neighbor] == 0:
                dfs(neighbor, path, path_set)
            elif visited[neighbor] == 1:
                # Cycle detected! Extract the cyclic portion of the path
                try:
                    start_idx = path.index(neighbor)
                    cycle = path[start_idx:] + [neighbor]
                    # Avoid adding identical cyclic permutations
                    cycle_sorted = sorted(cycle[:-1])
                    if not any(sorted(c[:-1]) == cycle_sorted for c in cycles):
                        cycles.append(cycle)
                except ValueError:
                    pass

        path_set.remove(node)
        path.pop()
        visited[node] = 2

    for node in dependency_graph:
        if visited[node] == 0:
            dfs(node, [], set())

    return cycles

def detect_large_classes(ast_data: Dict[str, Any], line_threshold: int = 150, method_threshold: int = 8) -> List[Dict[str, Any]]:
    """
    Identifies classes that are abnormally large in terms of lines of code or number of methods.
    """
    large_classes = []
    for filepath, data in ast_data.items():
        for cls in data.get("classes", []):
            lines = cls["end_line"] - cls["start_line"] + 1
            methods_count = len(cls.get("methods", []))
            if lines >= line_threshold or methods_count >= method_threshold:
                large_classes.append({
                    "file": filepath,
                    "class_name": cls["name"],
                    "lines": lines,
                    "methods_count": methods_count
                })
    return large_classes

def detect_high_complexity_modules(ast_data: Dict[str, Any], function_threshold: int = 10) -> List[Dict[str, Any]]:
    """
    Identifies modules (files) containing too many functions or classes, indicating potential high complexity.
    """
    complex_modules = []
    for filepath, data in ast_data.items():
        # Count global functions + methods across all classes in this file
        global_funcs = len(data.get("functions", []))
        methods_count = sum(len(cls.get("methods", [])) for cls in data.get("classes", []))
        total_functions = global_funcs + methods_count
        classes_count = len(data.get("classes", []))
        
        if total_functions >= function_threshold:
            complex_modules.append({
                "file": filepath,
                "total_functions": total_functions,
                "classes_count": classes_count
            })
    return complex_modules

def detect_architectural_violations(dependency_graph: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """
    Enforces layer boundary constraints on the repository structure.
    Layering definition:
    1. Low-level: src/utils, src/state, src/config, src/database (must not import agents/graph/main)
    2. Mid-level: src/agents (must not import graph/main)
    3. High-level/Orchestration: src/graph, main
    """
    violations = []
    for file, deps in dependency_graph.items():
        file_norm = file.replace("\\", "/")
        
        # 1. Low-level layer checks
        is_low_level = (
            "src/utils/" in file_norm or 
            file_norm.endswith("src/state.py") or 
            file_norm.endswith("src/config.py") or 
            file_norm.endswith("src/database.py")
        )
        if is_low_level:
            for dep in deps:
                dep_norm = dep.replace("\\", "/")
                if "src/agents/" in dep_norm or dep_norm.endswith("src/graph.py") or dep_norm.endswith("main.py"):
                    violations.append({
                        "file": file,
                        "violates": "Layer Boundary Violation",
                        "imported_file": dep,
                        "description": f"Low-level module '{file}' imports high-level module '{dep}'"
                    })
                    
        # 2. Mid-level layer checks
        elif "src/agents/" in file_norm:
            for dep in deps:
                dep_norm = dep.replace("\\", "/")
                if dep_norm.endswith("src/graph.py") or dep_norm.endswith("main.py"):
                    violations.append({
                        "file": file,
                        "violates": "Layer Boundary Violation",
                        "imported_file": dep,
                        "description": f"Agent module '{file}' imports orchestration module '{dep}'"
                    })
                    
    return violations

def calculate_maintainability_score(
    cycles: List[List[str]],
    violations: List[Dict[str, Any]],
    large_classes: List[Dict[str, Any]],
    complex_modules: List[Dict[str, Any]]
) -> int:
    """
    Computes a base maintainability score from 0 to 100 based on detected architectural anomalies.
    """
    score = 100
    
    # Deductions:
    # 1. Circular dependencies are highly critical: -15 each (max -45)
    score -= min(len(cycles) * 15, 45)
    
    # 2. Architectural layer violations: -10 each (max -30)
    score -= min(len(violations) * 10, 30)
    
    # 3. Large classes: -5 each (max -20)
    score -= min(len(large_classes) * 5, 20)
    
    # 4. Complex modules: -5 each (max -15)
    score -= min(len(complex_modules) * 5, 15)
    
    return max(score, 10)
