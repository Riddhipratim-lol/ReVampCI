"""
Repository Intelligence module for ReVampCI.
Analyzes repository structure and file contents to extract languages,
frameworks, build systems, dependencies, and metadata.
"""
import os
import json
import re
from typing import Dict, Any, List

# Standard extension mappings
EXTENSION_TO_LANGUAGE = {
    '.py': 'Python',
    '.js': 'JavaScript',
    '.mjs': 'JavaScript',
    '.cjs': 'JavaScript',
    '.ts': 'TypeScript',
    '.mts': 'TypeScript',
    '.cts': 'TypeScript',
    '.jsx': 'React (JS)',
    '.tsx': 'React (TS)',
    '.go': 'Go',
    '.rs': 'Rust',
    '.java': 'Java',
    '.kt': 'Kotlin',
    '.kts': 'Kotlin',
    '.swift': 'Swift',
    '.c': 'C',
    '.cpp': 'C++',
    '.cc': 'C++',
    '.cxx': 'C++',
    '.h': 'C/C++ Header',
    '.hpp': 'C++ Header',
    '.cs': 'C#',
    '.rb': 'Ruby',
    '.php': 'PHP',
    '.sh': 'Shell',
    '.bash': 'Shell',
    '.yml': 'YAML',
    '.yaml': 'YAML',
    '.json': 'JSON',
    '.toml': 'TOML',
    '.md': 'Markdown',
    '.html': 'HTML',
    '.css': 'CSS',
    '.sql': 'SQL'
}

def analyze_repository(repo_path: str, file_contents: Dict[str, str], repository_structure: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes the repository path, file structure, and file contents
    to detect languages, frameworks, build systems, dependencies, and metadata.
    """
    files = repository_structure.get("files", [])
    directories = repository_structure.get("directories", [])
    
    # 1. Language detection
    language_counts = {}
    language_sizes = {}
    for rel_path in files:
        _, ext = os.path.splitext(rel_path)
        lang = EXTENSION_TO_LANGUAGE.get(ext.lower(), 'Other')
        language_counts[lang] = language_counts.get(lang, 0) + 1
        
        full_path = os.path.join(repo_path, rel_path)
        try:
            size = os.path.getsize(full_path)
        except Exception:
            size = len(file_contents.get(rel_path, ''))
        language_sizes[lang] = language_sizes.get(lang, 0) + size
        
    detected_languages = sorted(list(language_counts.keys()))
    
    # 2. Build system detection
    build_systems = []
    # Python
    if "requirements.txt" in files:
        build_systems.append("pip (requirements.txt)")
    if "pyproject.toml" in files:
        toml_content = file_contents.get("pyproject.toml", "")
        if "poetry.core" in toml_content or "[tool.poetry]" in toml_content:
            build_systems.append("Poetry (pyproject.toml)")
        elif "hatchling" in toml_content:
            build_systems.append("Hatch (pyproject.toml)")
        elif "flit" in toml_content:
            build_systems.append("Flit (pyproject.toml)")
        elif "pdm" in toml_content:
            build_systems.append("PDM (pyproject.toml)")
        else:
            build_systems.append("setuptools (pyproject.toml)")
    if "setup.py" in files:
        build_systems.append("setuptools (setup.py)")
    if "uv.lock" in files:
        build_systems.append("uv (uv.lock)")
    
    # Node.js
    if "package-lock.json" in files:
        build_systems.append("npm (package-lock.json)")
    elif "yarn.lock" in files:
        build_systems.append("yarn (yarn.lock)")
    elif "pnpm-lock.yaml" in files:
        build_systems.append("pnpm (pnpm-lock.yaml)")
    elif "bun.lockb" in files:
        build_systems.append("bun (bun.lockb)")
    elif "package.json" in files:
        build_systems.append("npm/yarn/pnpm (package.json)")
        
    # Go
    if "go.mod" in files:
        build_systems.append("go build (go.mod)")
        
    # Rust
    if "Cargo.toml" in files:
        build_systems.append("cargo (Cargo.toml)")
        
    # Java
    if "pom.xml" in files:
        build_systems.append("Maven (pom.xml)")
    if "build.gradle" in files or "build.gradle.kts" in files:
        build_systems.append("Gradle")
        
    # 3. Dependency extraction
    dependencies = []
    
    # Python - requirements.txt
    if "requirements.txt" in files:
        req_content = file_contents.get("requirements.txt", "")
        for line in req_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-r") or line.startswith("-e"):
                continue
            match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)', line)
            if match:
                dep_name = match.group(1).strip()
                if dep_name not in dependencies:
                    dependencies.append(dep_name)
                    
    # Python - pyproject.toml
    if "pyproject.toml" in files:
        toml_content = file_contents.get("pyproject.toml", "")
        try:
            import tomllib
            parsed_toml = tomllib.loads(toml_content)
            # Standard dependencies
            project_deps = parsed_toml.get("project", {}).get("dependencies", [])
            for dep in project_deps:
                match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)', dep)
                if match:
                    dep_name = match.group(1).strip()
                    if dep_name not in dependencies:
                        dependencies.append(dep_name)
            # Poetry dependencies
            poetry_deps = parsed_toml.get("tool", {}).get("poetry", {}).get("dependencies", {})
            for dep_name in poetry_deps.keys():
                if dep_name != "python" and dep_name not in dependencies:
                    dependencies.append(dep_name)
        except Exception:
            # Fallback regex parsing
            deps_match = re.findall(r'dependencies\s*=\s*\[(.*?)\]', toml_content, re.DOTALL)
            for dm in deps_match:
                for line in dm.splitlines():
                    line = line.strip().strip('"').strip("'").strip(',')
                    match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)', line)
                    if match:
                        dep_name = match.group(1).strip()
                        if dep_name not in dependencies:
                            dependencies.append(dep_name)
                            
    # Node.js - package.json
    if "package.json" in files:
        pkg_content = file_contents.get("package.json", "{}")
        try:
            pkg_data = json.loads(pkg_content)
            deps = pkg_data.get("dependencies", {})
            dev_deps = pkg_data.get("devDependencies", {})
            for d in list(deps.keys()) + list(dev_deps.keys()):
                if d not in dependencies:
                    dependencies.append(d)
        except Exception:
            pass
            
    # Go - go.mod
    if "go.mod" in files:
        go_mod_content = file_contents.get("go.mod", "")
        require_block_match = re.search(r'require\s*\((.*?)\)', go_mod_content, re.DOTALL)
        if require_block_match:
            for line in require_block_match.group(1).splitlines():
                line = line.strip()
                if line and not line.startswith("//"):
                    parts = line.split()
                    if parts:
                        dep_name = parts[0]
                        if dep_name not in dependencies:
                            dependencies.append(dep_name)
        single_requires = re.findall(r'^require\s+([^\s\(\)]+)', go_mod_content, re.MULTILINE)
        for dep in single_requires:
            if dep not in dependencies:
                dependencies.append(dep)
                
    # Rust - Cargo.toml
    if "Cargo.toml" in files:
        cargo_content = file_contents.get("Cargo.toml", "")
        try:
            import tomllib
            parsed_cargo = tomllib.loads(cargo_content)
            cargo_deps = parsed_cargo.get("dependencies", {})
            for dep_name in cargo_deps.keys():
                if dep_name not in dependencies:
                    dependencies.append(dep_name)
            dev_deps = parsed_cargo.get("dev-dependencies", {})
            for dep_name in dev_deps.keys():
                if dep_name not in dependencies:
                    dependencies.append(dep_name)
        except Exception:
            pass
            
    # 4. Framework detection
    frameworks = []
    # Python frameworks
    if any(f in files or f.endswith("/manage.py") for f in ["manage.py", "wsgi.py", "settings.py"]):
        frameworks.append("Django")
    for dep in dependencies:
        if dep.lower() == "fastapi":
            frameworks.append("FastAPI")
        elif dep.lower() == "flask":
            frameworks.append("Flask")
        elif dep.lower() == "pytest":
            frameworks.append("pytest")
            
    # JavaScript/TypeScript frameworks
    for dep in dependencies:
        if dep.lower() in ("react", "react-dom"):
            if "React" not in frameworks:
                frameworks.append("React")
        elif dep.lower() == "vue":
            frameworks.append("Vue")
        elif dep.lower() == "@angular/core":
            frameworks.append("Angular")
        elif dep.lower() == "svelte":
            frameworks.append("Svelte")
        elif dep.lower() == "express":
            frameworks.append("Express")
        elif dep.lower() == "next":
            frameworks.append("Next.js")
        elif dep.lower() == "nuxt":
            frameworks.append("Nuxt.js")
        elif dep.lower() == "@nestjs/core":
            frameworks.append("NestJS")
            
    # Go frameworks
    for dep in dependencies:
        if "github.com/gin-gonic/gin" in dep:
            frameworks.append("Gin")
        elif "github.com/gofiber/fiber" in dep:
            frameworks.append("Fiber")
        elif "github.com/labstack/echo" in dep:
            frameworks.append("Echo")
            
    # Rust frameworks
    for dep in dependencies:
        if dep.lower() == "actix-web":
            frameworks.append("Actix-web")
        elif dep.lower() == "axum":
            frameworks.append("Axum")
        elif dep.lower() == "rocket":
            frameworks.append("Rocket")
            
    # 5. Metadata collection
    total_files = len(files)
    total_dirs = len(directories)
    total_loc = 0
    for rel_path, content in file_contents.items():
        total_loc += len(content.splitlines())
        
    primary_lang = "Unknown"
    if language_sizes:
        primary_lang = max(language_sizes, key=language_sizes.get)
        
    entry_points = []
    possible_entries = ["main.py", "app.py", "index.js", "main.go", "src/index.ts", "src/main.ts", "server.js", "app.js"]
    for entry in possible_entries:
        if entry in files:
            entry_points.append(entry)
            
    project_metadata = {
        "total_files": total_files,
        "total_directories": total_dirs,
        "total_loc": total_loc,
        "primary_language": primary_lang,
        "entry_points": entry_points,
        "build_systems": build_systems
    }
    
    return {
        "languages": detected_languages,
        "frameworks": frameworks,
        "dependencies": dependencies,
        "project_metadata": project_metadata
    }
