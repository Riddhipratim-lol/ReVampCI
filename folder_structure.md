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
├── folder_structure.md          # [This File] High-level directory structure and explanation
├── implementation.md            # Detailed implementation log/notes of the system
├── main.py                      # CLI runner to execute the refactoring pipeline
├── src/                         # Core application package
│   ├── __init__.py
│   ├── config.py                # Configuration loader and environment schema
│   ├── database.py              # SQLite storage/state persistence configuration
│   ├── main.py                  # FastAPI service entry point (placeholder/future API)
│   ├── state.py                 # LangGraph state schema definition
│   ├── graph.py                 # LangGraph workflow router and compiler
│   ├── agents/                  # LangGraph node agent implementations
│   │   ├── __init__.py
│   │   ├── codespace.py         # Codespace setup node
│   │   ├── parser.py            # AST parsing and structure mapping agent node
│   │   ├── analysis.py          # Deep code analysis, symbol table and dependency graph builder
│   │   ├── critic.py            # Code smell, duplicate analysis, and refactoring planner agent node
│   │   ├── coding.py            # Refactoring execution agent node
│   │   ├── tester.py            # Automated build/test running and verification agent node
│   │   ├── report.py            # Markdown refactoring report generation node
│   │   └── pr.py                # GitHub branch, commit, and Pull Request creation agent node (placeholder/WIP)
│   └── utils/                   # Shared utility modules
│       ├── __init__.py
│       ├── git_helper.py        # Wrapper for repository clone/commit/branch actions (GitPython)
│       ├── github_api.py        # Client for GitHub REST API interactions
│       ├── ast_parser.py        # AST parsing and deep source code mapping (Tree-sitter/AST)
│       ├── repository_intelligence.py # Extracts languages, frameworks, build systems, and dependencies
│       └── logger.py            # Standard structured JSON logger configuration
└── tests/                       # Project test suites
    ├── __init__.py
    ├── test_agents.py           # Unit tests for individual agent node states
    ├── test_api.py              # Integration tests for FastAPI endpoints
    ├── test_phase1_flow.py      # Integration test for the core Phase 1 workflow
    └── test_phase3_analysis.py  # Unit/integration tests for AST analysis and deep code parsing
```

---

## File and Package Descriptions

### Root Files
- **`main.py`**: CLI command-line runner to execute the end-to-end refactoring pipeline for a given repository.
- **`folder_structure.md`**: Outlines the repository layout and details on the roles of each module.
- **`implementation.md`**: Serves as a record of architecture, flow, design, and changes during implementation.

### Core Package (`src/`)
- **`config.py`**: Reads and validates environment variables defined in `.env` (such as `GEMINI_API_KEY`, `CUSTOM_GITHUB_TOKEN`, and `DATABASE_URL`).
- **`database.py`**: Configures local persistence (SQLite) for storing execution history, issues log, and graph checkpoints.
- **`main.py`**: FastAPI application entrypoint (placeholder/future REST API endpoints).
- **`state.py`**: Defines the shared LangGraph State object that maps:
  - Repository metadata (`repo_url`, `repo_path`).
  - Extracted code structure (`repository_structure`, `file_contents`, `dependency_graph`, `ast_data`, `symbol_table`).
  - Audit/refactoring tasks (`identified_issues`, `refactoring_tasks`).
  - Validation logs (`test_results`, `build_logs`, `error_logs`).
  - Final integration details (`pull_request_summary`, `final_report`).
- **`graph.py`**: Compiles nodes from `src/agents/` into a stateful LangGraph structure. Implements the execution sequence and any conditional loops.

### Agent Nodes (`src/agents/`)
- **`codespace.py`**: Handles repository preparation. Clones target codebases into workspace paths and installs their custom dependencies.
- **`parser.py`**: Performs high-level parsing, detects repository metadata, dependencies, languages, and frameworks.
- **`analysis.py`**: Performs deep code analysis using AST parsers to generate symbol tables and mapping dependency graphs of functions and classes.
- **`critic.py`**: Inspects files and AST details, calling LLMs to detect duplicate functions, over-complex files, and code smells, outputting a structured list of tasks.
- **`coding.py`**: Executes proposed refactoring tasks. Uses failure logs from `tester` to fix syntax errors or broken tests in a correction loop.
- **`tester.py`**: Performs validation by running subprocess compiler/testing commands within the target repo environment.
- **`report.py`**: Gathers all execution history, modified files, identified issues, and test results, and generates a structured markdown final report summarizing the refactoring session.
- **`pr.py`**: Creates a git branch with all modifications, commits changes with summaries, pushes, and creates a Pull Request via GitHub REST APIs (currently stub/WIP).

### Utilities (`src/utils/`)
- **`git_helper.py`**: Encapsulates common Git operations using `GitPython`.
- **`github_api.py`**: Interface for the GitHub REST API to automate PR description postings.
- **`ast_parser.py`**: Language-specific tree-sitter or core `ast` module wrappers.
- **`repository_intelligence.py`**: Checks file patterns, imports, build locks, and configuration files to discover languages, packages, and frameworks.
- **`logger.py`**: Unified logger for structured tracing across FastAPI endpoints and Graph node transitions.

### Test Suites (`tests/`)
- **`test_agents.py`**: Unit tests verifying the individual agent nodes' state transformations.
- **`test_api.py`**: Placeholder for testing FastAPI endpoints.
- **`test_phase1_flow.py`**: Full LangGraph execution test simulating a repo setup, parsing, criticizing, coding, testing, and reporting loop.
- **`test_phase3_analysis.py`**: Tests checking symbol tables and internal dependency graph construction using the AST parsers.
