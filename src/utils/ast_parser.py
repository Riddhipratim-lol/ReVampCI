"""
AST parsing utility using Python's built-in AST / tree-sitter.
Analyzes code constructs, variables, function signatures, and builds structural representation.
"""
import os
import re
from typing import Dict, Any, List, Set

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize tree-sitter parsers if packages are available
PY_PARSER = None
JS_PARSER = None

try:
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser as TSParser
    PY_LANGUAGE = Language(tspython.language())
    PY_PARSER = TSParser(PY_LANGUAGE)
    logger.info("Tree-sitter Python parser successfully loaded.")
except Exception as e:
    logger.warning(f"Failed to load Tree-sitter Python parser: {e}. Falling back to regex parser.")

try:
    import tree_sitter_javascript as tsjs
    from tree_sitter import Language, Parser as TSParser
    JS_LANGUAGE = Language(tsjs.language())
    JS_PARSER = TSParser(JS_LANGUAGE)
    logger.info("Tree-sitter JavaScript parser successfully loaded.")
except Exception as e:
    logger.warning(f"Failed to load Tree-sitter JavaScript parser: {e}. Falling back to regex parser.")


def parse_parameters_python(params_node) -> List[str]:
    """Helper to extract parameter names from a Python parameter list node."""
    params = []
    if not params_node:
        return params
    for child in params_node.children:
        if child.type in ("identifier", "typed_parameter", "default_parameter", "typed_default_parameter", "list_splat_pattern", "dictionary_splat_pattern"):
            # A simple way to get parameter name: split on ':' (type annotations) and '=' (default values)
            p_text = child.text.decode("utf-8", errors="replace").strip()
            name = p_text.split(":")[0].split("=")[0].strip().lstrip("*")
            if name and name not in (",", "(", ")"):
                params.append(name)
    return params


def parse_parameters_js(params_node) -> List[str]:
    """Helper to extract parameter names from a JS/TS parameter list node."""
    params = []
    if not params_node:
        return params
    for child in params_node.children:
        if child.type in ("identifier", "assignment_pattern", "rest_pattern", "formal_parameter"):
            p_text = child.text.decode("utf-8", errors="replace").strip()
            name = p_text.split("=")[0].strip().lstrip(".")
            if name and name not in (",", "(", ")", "{", "}"):
                params.append(name)
    return params


def parse_python_with_treesitter(content: str) -> Dict[str, Any]:
    """Parse Python code using tree-sitter."""
    if not PY_PARSER:
        raise RuntimeError("Python tree-sitter parser not initialized")
    
    tree = PY_PARSER.parse(bytes(content, "utf-8"))
    classes = []
    functions = []
    imports = []
    
    def traverse(node, current_class=None):
        if node.type == "class_definition":
            cls_name_node = node.child_by_field_name("name")
            cls_name = cls_name_node.text.decode("utf-8", errors="replace") if cls_name_node else "Unknown"
            
            cls_info = {
                "name": cls_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "methods": []
            }
            classes.append(cls_info)
            
            # Traverse class body
            body_node = node.child_by_field_name("body")
            if body_node:
                for child in body_node.children:
                    traverse(child, current_class=cls_info)
            return
            
        elif node.type == "function_definition":
            func_name_node = node.child_by_field_name("name")
            func_name = func_name_node.text.decode("utf-8", errors="replace") if func_name_node else "Unknown"
            params_node = node.child_by_field_name("parameters")
            params = parse_parameters_python(params_node)
            
            func_info = {
                "name": func_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "parameters": params
            }
            
            if current_class is not None:
                current_class["methods"].append(func_info)
            else:
                functions.append(func_info)
            return
            
        elif node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(child.text.decode("utf-8", errors="replace"))
                elif child.type == "aliased_import":
                    for sub in child.children:
                        if sub.type == "dotted_name":
                            imports.append(sub.text.decode("utf-8", errors="replace"))
            return
            
        elif node.type == "import_from_statement":
            import_from_str = ""
            for child in node.children:
                if child.type in ("relative_import", "dotted_name"):
                    import_from_str = child.text.decode("utf-8", errors="replace")
                    break
            if import_from_str:
                imports.append(import_from_str)
            return
            
        for child in node.children:
            traverse(child, current_class)

    traverse(tree.root_node)
    return {
        "classes": classes,
        "functions": functions,
        "imports": imports
    }


def parse_javascript_with_treesitter(content: str) -> Dict[str, Any]:
    """Parse JavaScript code using tree-sitter."""
    if not JS_PARSER:
        raise RuntimeError("JS tree-sitter parser not initialized")
        
    tree = JS_PARSER.parse(bytes(content, "utf-8"))
    classes = []
    functions = []
    imports = []
    
    def traverse(node, current_class=None):
        if node.type == "class_declaration":
            cls_name_node = node.child_by_field_name("name")
            cls_name = cls_name_node.text.decode("utf-8", errors="replace") if cls_name_node else "Unknown"
            
            cls_info = {
                "name": cls_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "methods": []
            }
            classes.append(cls_info)
            
            body_node = node.child_by_field_name("body")
            if body_node:
                for child in body_node.children:
                    traverse(child, current_class=cls_info)
            return
            
        elif node.type == "method_definition":
            method_name_node = node.child_by_field_name("name")
            method_name = method_name_node.text.decode("utf-8", errors="replace") if method_name_node else "Unknown"
            params_node = node.child_by_field_name("parameters")
            params = parse_parameters_js(params_node)
            
            method_info = {
                "name": method_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "parameters": params
            }
            if current_class is not None:
                current_class["methods"].append(method_info)
            else:
                functions.append(method_info)
            return
            
        elif node.type in ("function_declaration", "generator_function_declaration"):
            func_name_node = node.child_by_field_name("name")
            func_name = func_name_node.text.decode("utf-8", errors="replace") if func_name_node else "Unknown"
            params_node = node.child_by_field_name("parameters")
            params = parse_parameters_js(params_node)
            
            func_info = {
                "name": func_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "parameters": params
            }
            functions.append(func_info)
            return
            
        elif node.type == "import_statement":
            source_node = node.child_by_field_name("source")
            if source_node:
                source_val = source_node.text.decode("utf-8", errors="replace").strip("'\"")
                imports.append(source_val)
            return
            
        elif node.type == "call_expression":
            # Detect require("./path")
            function_node = node.child_by_field_name("function")
            if function_node and function_node.text == b"require":
                arguments_node = node.child_by_field_name("arguments")
                if arguments_node and len(arguments_node.children) >= 2:
                    # require arguments: "(", string, ")"
                    arg_string = arguments_node.children[1]
                    if arg_string.type == "string":
                        source_val = arg_string.text.decode("utf-8", errors="replace").strip("'\"")
                        imports.append(source_val)
            
        for child in node.children:
            traverse(child, current_class)

    traverse(tree.root_node)
    return {
        "classes": classes,
        "functions": functions,
        "imports": imports
    }


def parse_fallback_regex(content: str, language: str) -> Dict[str, Any]:
    """Fallback regex parser for general or unsupported languages."""
    classes = []
    functions = []
    imports = []
    
    lines = content.splitlines()
    
    if language.lower() in ("python", "py"):
        # Basic Python regex extraction
        for i, line in enumerate(lines):
            line_num = i + 1
            # Class match
            cls_match = re.match(r'^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)', line)
            if cls_match:
                classes.append({
                    "name": cls_match.group(1),
                    "start_line": line_num,
                    "end_line": line_num,  # Fallback approximation
                    "methods": []
                })
                continue
            
            # Function match
            func_match = re.match(r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)', line)
            if func_match:
                func_name = func_match.group(1)
                raw_params = func_match.group(2)
                params = [p.split(":")[0].split("=")[0].strip().lstrip("*") for p in raw_params.split(",") if p.strip()]
                params = [p for p in params if p and p not in ("self", "cls")]
                
                func_info = {
                    "name": func_name,
                    "start_line": line_num,
                    "end_line": line_num,
                    "parameters": params
                }
                
                # Check if nested in a class
                if classes and line.startswith("    "):
                    classes[-1]["methods"].append(func_info)
                else:
                    functions.append(func_info)
                continue
                
            # Imports
            imp_match1 = re.match(r'^\s*import\s+([a-zA-Z0-9_\.,\s]+)', line)
            if imp_match1:
                for parts in imp_match1.group(1).split(","):
                    p = parts.split("as")[0].strip()
                    if p:
                        imports.append(p)
                continue
                
            imp_match2 = re.match(r'^\s*from\s+([a-zA-Z0-9_\.]+)\s+import', line)
            if imp_match2:
                imports.append(imp_match2.group(1))
                
    elif language.lower() in ("javascript", "js", "typescript", "ts", "react (js)", "react (ts)"):
        # Basic JS/TS regex extraction
        for i, line in enumerate(lines):
            line_num = i + 1
            # Class match
            cls_match = re.search(r'\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)', line)
            if cls_match:
                classes.append({
                    "name": cls_match.group(1),
                    "start_line": line_num,
                    "end_line": line_num,
                    "methods": []
                })
                continue
                
            # Function match
            func_match = re.search(r'\bfunction\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)', line)
            if func_match:
                func_name = func_match.group(1)
                raw_params = func_match.group(2)
                params = [p.split("=")[0].strip() for p in raw_params.split(",") if p.strip()]
                functions.append({
                    "name": func_name,
                    "start_line": line_num,
                    "end_line": line_num,
                    "parameters": params
                })
                continue
                
            # Arrow function
            arrow_match = re.search(r'\b(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:\((.*?)\)|([a-zA-Z_][a-zA-Z0-9_]*))\s*=>', line)
            if arrow_match:
                func_name = arrow_match.group(1)
                raw_params = arrow_match.group(2) or arrow_match.group(3) or ""
                params = [p.strip() for p in raw_params.split(",") if p.strip()]
                functions.append({
                    "name": func_name,
                    "start_line": line_num,
                    "end_line": line_num,
                    "parameters": params
                })
                continue
                
            # JS imports
            js_imp1 = re.search(r'\bimport\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]', line)
            if js_imp1:
                imports.append(js_imp1.group(1))
                continue
            js_imp2 = re.search(r'\brequire\([\'"]([^\'"]+)[\'"]\)', line)
            if js_imp2:
                imports.append(js_imp2.group(1))
                
    else:
        # Generic fallback for other languages (Go, Rust, C++, Swift, etc.)
        # Extract anything that looks like import/class/func
        for i, line in enumerate(lines):
            line_num = i + 1
            # Class-like: class Foo, struct Foo, type Foo
            cls_match = re.search(r'\b(?:class|struct|type)\s+([a-zA-Z_][a-zA-Z0-9_]*)', line)
            if cls_match:
                classes.append({
                    "name": cls_match.group(1),
                    "start_line": line_num,
                    "end_line": line_num,
                    "methods": []
                })
                continue
            # Func-like: func Foo, function Foo, fn Foo, void Foo
            func_match = re.search(r'\b(?:func|fn|function|void|int|string)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', line)
            if func_match:
                functions.append({
                    "name": func_match.group(1),
                    "start_line": line_num,
                    "end_line": line_num,
                    "parameters": []
                })
                
    return {
        "classes": classes,
        "functions": functions,
        "imports": imports
    }


def parse_file_to_ast(filepath: str, content: str) -> Dict[str, Any]:
    """
    Parses a single file content and returns its AST structure: classes, functions, and imports.
    Chooses between Python/JS tree-sitter or regex fallback based on file extension.
    """
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    
    try:
        if ext == ".py" and PY_PARSER:
            return parse_python_with_treesitter(content)
        elif ext in (".js", ".jsx") and JS_PARSER:
            return parse_javascript_with_treesitter(content)
        elif ext in (".ts", ".tsx") and JS_PARSER:
            # We can use JS parser as approximation for TS files
            return parse_javascript_with_treesitter(content)
    except Exception as e:
        logger.warning(f"Tree-sitter failed for {filepath}: {e}. Falling back to regex.")
        
    # Language identification for fallback regex
    language = "other"
    if ext == ".py":
        language = "python"
    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        language = "javascript"
        
    return parse_fallback_regex(content, language)


def build_symbol_table(ast_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Builds a unified symbol table from the AST data, mapping each symbol name
    to a list of definitions where it occurs in the project.
    """
    symbol_table: Dict[str, List[Dict[str, Any]]] = {}
    
    for filepath, data in ast_data.items():
        # Index Classes
        for cls in data.get("classes", []):
            name = cls["name"]
            symbol_info = {
                "file": filepath,
                "line": cls["start_line"],
                "kind": "class",
                "signature": []
            }
            symbol_table.setdefault(name, []).append(symbol_info)
            
            # Index Methods within Class
            for method in cls.get("methods", []):
                method_name = method["name"]
                method_info = {
                    "file": filepath,
                    "line": method["start_line"],
                    "kind": "method",
                    "container": name,
                    "signature": method.get("parameters", [])
                }
                symbol_table.setdefault(method_name, []).append(method_info)
                
        # Index Functions
        for func in data.get("functions", []):
            name = func["name"]
            symbol_info = {
                "file": filepath,
                "line": func["start_line"],
                "kind": "function",
                "signature": func.get("parameters", [])
            }
            symbol_table.setdefault(name, []).append(symbol_info)
            
    return symbol_table


def build_dependency_graph(repo_path: str, files: List[str], file_contents: Dict[str, str], ast_data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Resolves imports in each file to create a project-internal dependency graph.
    Maps each file path to a list of other file paths in the repository that it imports.
    """
    dependency_graph: Dict[str, List[str]] = {}
    
    # Store set of files for quick check
    files_set = set(files)
    
    # Create module-to-file lookup (e.g. "src.utils.logger" -> "src/utils/logger.py")
    # For Python files, map dot notations
    python_modules: Dict[str, str] = {}
    for f in files:
        if f.endswith(".py"):
            mod_path = f[:-3].replace("/", ".")
            python_modules[mod_path] = f
            # Also handle __init__.py package name mapping
            if f.endswith("__init__.py"):
                pkg_path = os.path.dirname(f).replace("/", ".")
                if pkg_path:
                    python_modules[pkg_path] = f
                    
    for filepath, data in ast_data.items():
        dependencies: Set[str] = set()
        file_dir = os.path.dirname(filepath)
        
        for imp in data.get("imports", []):
            resolved = False
            
            # Case 1: Python dot import (absolute or relative)
            if filepath.endswith(".py"):
                # Handle relative imports e.g., ".utils" or "..agents"
                if imp.startswith("."):
                    # Count leading dots
                    dots_count = 0
                    for char in imp:
                        if char == ".":
                            dots_count += 1
                        else:
                            break
                    rest_of_imp = imp[dots_count:]
                    
                    # Resolve directory based on dots
                    parts = file_dir.split("/") if file_dir else []
                    if dots_count > 1 and len(parts) >= (dots_count - 1):
                        target_parts = parts[:-(dots_count - 1)]
                    else:
                        target_parts = parts
                    
                    resolved_dir = "/".join(target_parts)
                    
                    # Try matching resolved path
                    sub_path = rest_of_imp.replace(".", "/")
                    candidate = os.path.join(resolved_dir, sub_path).strip("/")
                    
                    for ext_c in (f"{candidate}.py", f"{candidate}/__init__.py"):
                        if ext_c in files_set:
                            dependencies.add(ext_c)
                            resolved = True
                            break
                            
                if not resolved:
                    # Try direct python module lookup (absolute import)
                    if imp in python_modules:
                        dependencies.add(python_modules[imp])
                        resolved = True
                    else:
                        # Try partial package match, e.g. imp is "src.utils.logger.get_logger" -> "src.utils.logger"
                        parts = imp.split(".")
                        for length in range(len(parts) - 1, 0, -1):
                            prefix = ".".join(parts[:length])
                            if prefix in python_modules:
                                dependencies.add(python_modules[prefix])
                                resolved = True
                                break
                                
            # Case 2: JavaScript/TypeScript relative path import (e.g. "./utils", "../config")
            elif filepath.endswith((".js", ".jsx", ".ts", ".tsx")) and (imp.startswith("./") or imp.startswith("../")):
                candidate_base = os.path.normpath(os.path.join(file_dir, imp))
                
                # Check different JS/TS extensions
                for ext in (".js", ".jsx", ".ts", ".tsx", "/index.js", "/index.ts", "/index.jsx", "/index.tsx"):
                    cand = f"{candidate_base}{ext}"
                    if cand in files_set:
                        dependencies.add(cand)
                        resolved = True
                        break
                        
            # Case 3: Generic suffix/absolute path heuristic matching
            if not resolved:
                # If the import string is a simple name, check if any file in the repo ends with that name
                # E.g. importing "config" matches "src/config.py"
                imp_clean = imp.replace(".", "/").strip("/")
                for f in files:
                    # Don't match the file with itself
                    if f == filepath:
                        continue
                    # Match suffix, e.g. "utils/logger.py" matches import "logger"
                    f_no_ext, _ = os.path.splitext(f)
                    if f_no_ext.endswith(imp_clean) or imp_clean.endswith(f_no_ext):
                        dependencies.add(f)
                        break
                        
        dependency_graph[filepath] = sorted(list(dependencies))
        
    return dependency_graph


def analyze_repo_deeply(repo_path: str, files: List[str], file_contents: Dict[str, str]) -> Dict[str, Any]:
    """
    Main entry point to perform deep structural analysis of a repository.
    Generates AST data, a unified symbol table, and a project-internal dependency graph.
    """
    logger.info(f"Starting deep analysis for repository: {repo_path}")
    
    # 1. Generate AST data for each file
    ast_data = {}
    for filepath, content in file_contents.items():
        ast_data[filepath] = parse_file_to_ast(filepath, content)
        
    # 2. Build global symbol table
    symbol_table = build_symbol_table(ast_data)
    
    # 3. Build project dependency graph
    dependency_graph = build_dependency_graph(repo_path, files, file_contents, ast_data)
    
    logger.info(f"Deep analysis complete. Indexed {len(symbol_table)} symbols and mapped {len(dependency_graph)} modules.")
    
    return {
        "ast_data": ast_data,
        "symbol_table": symbol_table,
        "dependency_graph": dependency_graph
    }
