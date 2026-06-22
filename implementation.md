# ReVampCI Project Implementation Details

This document outlines the generated folder structure and the purpose of each file and folder in the **Autonomous Code Refactoring & CI/CD Guard Agent** project.

---

## Directory Structure

```
ReVampCI/
├── .env                         # Current local environment configuration
├── .env.template                # Template for environment variables (version-controlled)
├── pyproject.toml               # Poetry/Project configuration
├── requirements.txt             # Project Python dependencies
├── Project_Vision.md            # Vision document defining system requirements
├── implementation.md            # [This File] High-level architecture and file layout details
├── src/                         # Core application package
│   ├── __init__.py
│   ├── config.py                # Configuration loader and environment schema
│   ├── database.py              # SQLite storage/state persistence configuration
│   ├── main.py                  # FastAPI service entry point
│   ├── state.py                 # LangGraph state schema definition
│   ├── graph.py                 # LangGraph workflow router and compiler
│   ├── agents/                  # LangGraph node agent implementations
│   │   ├── __init__.py
│   │   ├── codespace.py         # Codespace setup node
│   │   ├── parser.py            # AST parsing and structure mapping agent node
│   │   ├── critic.py            # Code smell, duplicate analysis, and refactoring planner agent node
│   │   ├── coding.py            # Refactoring execution agent node
│   │   ├── tester.py            # Automated build/test running and verification agent node
│   │   └── pr.py                # GitHub branch, commit, and Pull Request creation agent node
│   └── utils/                   # Shared utility modules
│       ├── __init__.py
│       ├── git_helper.py        # Wrapper for repository clone/commit/branch actions (GitPython)
│       ├── github_api.py        # Client for GitHub REST API interactions
│       ├── ast_parser.py        # AST parsing and source code mapping (Tree-sitter/AST)
│       └── logger.py            # Standard structured JSON logger configuration
└── tests/                       # Project test suites
    ├── __init__.py
    ├── test_agents.py           # Unit tests for individual agent node states
    └── test_api.py              # Integration tests for FastAPI endpoints
```

---

## File and Package Descriptions

### Core Package (`src/`)
- **`config.py`**: Reads and validates environment variables defined in `.env` (such as `GEMINI_API_KEY`, `CUSTOM_GITHUB_TOKEN`, and `DATABASE_URL`).
- **`database.py`**: Configures local persistence (SQLite) for storing execution history, issues log, and graph checkpoints.
- **`main.py`**: Hosts the FastAPI server. It exposes endpoints to trigger the refactoring workflow for a repository URL and query execution status.
- **`state.py`**: Defines the shared LangGraph State object that maps:
  - Repository metadata (`repo_url`, `repo_path`).
  - Extracted code structure (`repository_structure`, `file_contents`, `dependency_graph`).
  - Audit/refactoring tasks (`identified_issues`, `refactoring_tasks`).
  - Validation logs (`test_results`, `build_logs`, `error_logs`).
  - Final integration details (`pull_request_summary`).
- **`graph.py`**: Compiles nodes from `src/agents/` into a stateful LangGraph structure. Implements conditional loops to redirect execution back to the Coding Agent if the Tester Agent reports build or test failures.

### Agent Nodes (`src/agents/`)
- **`codespace.py`**: Handles repository preparation. Clones target codebases into workspace paths and installs their custom dependencies.
- **`parser.py`**: Inspects files, builds AST representation using Tree-sitter or standard Python AST libraries, and builds a dependency map of functions/classes.
- **`critic.py`**: Inspects files and AST details, calling LLMs to detect duplicate functions, over-complex files, and code smells, outputting structured list of tasks.
- **`coding.py`**: Executes proposed refactoring tasks. Uses failure logs from `tester` to fix syntax errors or broken tests in a correction loop.
- **`tester.py`**: Performs validation by running subprocess compiler/testing commands within the target repo environment.
- **`pr.py`**: Creates a git branch with all modifications, commits changes with summaries, pushes, and creates a Pull Request via GitHub REST APIs.

### Utilities (`src/utils/`)
- **`git_helper.py`**: Encapsulates common Git operations using `GitPython`.
- **`github_api.py`**: Interface for the GitHub REST API to automate PR description postings.
- **`ast_parser.py`**: Language-specific tree-sitter or core `ast` module wrappers.
- **`logger.py`**: Unified logger for structured tracing across FastAPI endpoints and Graph node transitions.
