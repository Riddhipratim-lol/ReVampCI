"""
Tester Agent node implementation.
Acts as a quality gate by running compilation, test suites, capturing build logs,
errors, and results to feedback into the state.
"""
import os
import sys
import subprocess
import re
from typing import Dict, Any, List
from src.state import GraphState
from src.utils.logger import get_logger

logger = get_logger(__name__)

def parse_pytest_output(output: str):
    # Match lines like "=== 1 failed, 2 passed in 0.12s ==="
    # Or "=== 2 passed in 0.05s ==="
    # Or "=== 1 failed in 0.05s ==="
    summary_pattern = re.compile(r"===\s*(.*?)\s*in\s+[\d\.]+s\s*===")
    match = summary_pattern.search(output)
    
    passed = 0
    failed = 0
    
    if match:
        summary_str = match.group(1)
        passed_match = re.search(r"(\d+)\s+passed", summary_str)
        if passed_match:
            passed = int(passed_match.group(1))
            
        failed_match = re.search(r"(\d+)\s+failed", summary_str)
        if failed_match:
            failed = int(failed_match.group(1))
            
        skipped_match = re.search(r"(\d+)\s+skipped", summary_str)
        skipped = int(skipped_match.group(1)) if skipped_match else 0
        total = passed + failed + skipped
        return total, passed, failed
    else:
        # Fallback regex
        passed_match = re.search(r"(\d+)\s+passed", output)
        failed_match = re.search(r"(\d+)\s+failed", output)
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        return passed + failed, passed, failed

def parse_unittest_output(output: str):
    # Match "Ran X tests in Ys"
    run_match = re.search(r"Ran\s+(\d+)\s+tests?", output)
    if not run_match:
        return 0, 0, 0
    
    total = int(run_match.group(1))
    
    # Check if OK
    if "OK" in output:
        return total, total, 0
        
    # Check if FAILED
    failed_match = re.search(r"FAILED\s+\((?:failures=(\d+))?(?:,\s*errors=(\d+))?\)", output)
    failed = 0
    if failed_match:
        failures = int(failed_match.group(1)) if failed_match.group(1) else 0
        errors = int(failed_match.group(2)) if failed_match.group(2) else 0
        failed = failures + errors
        
    passed = total - failed
    return total, passed, failed

def tester_node(state: GraphState) -> Dict[str, Any]:
    """
    Detects the testing framework in the repository, runs the tests,
    captures logs and failure details, and updates the graph state.
    """
    logger.info("tester_node running")
    repo_path = state.get("repo_path")
    
    if not repo_path or not os.path.exists(repo_path):
        error_msg = f"Repository path {repo_path} does not exist."
        logger.error(error_msg)
        return {
            "test_results": {
                "success": False,
                "framework": "unknown",
                "summary": error_msg,
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "failures": [error_msg]
            },
            "build_logs": error_msg
        }

    # Framework detection
    framework = "unknown"
    cmd = []
    
    # 1. Check for Python project
    has_py = False
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "venv", ".venv", "__pycache__", "build", "dist")]
        if any(f.endswith(".py") for f in files):
            has_py = True
            break
            
    if has_py:
        use_pytest = False
        if os.path.exists(os.path.join(repo_path, "pytest.ini")) or os.path.exists(os.path.join(repo_path, "conftest.py")):
            use_pytest = True
        else:
            req_path = os.path.join(repo_path, "requirements.txt")
            pyproj_path = os.path.join(repo_path, "pyproject.toml")
            if os.path.exists(req_path):
                with open(req_path, "r", errors="ignore") as f:
                    if "pytest" in f.read():
                        use_pytest = True
            if not use_pytest and os.path.exists(pyproj_path):
                with open(pyproj_path, "r", errors="ignore") as f:
                    if "pytest" in f.read():
                        use_pytest = True
                        
        if use_pytest:
            framework = "pytest"
            cmd = [sys.executable, "-m", "pytest", "--tb=short"]
        else:
            framework = "unittest"
            cmd = [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"]
            
    # 2. Check for other project types
    elif os.path.exists(os.path.join(repo_path, "package.json")):
        framework = "npm"
        cmd = ["npm", "test"]
    elif os.path.exists(os.path.join(repo_path, "go.mod")):
        framework = "go"
        cmd = ["go", "test", "./..."]
    elif os.path.exists(os.path.join(repo_path, "Cargo.toml")):
        framework = "cargo"
        cmd = ["cargo", "test"]
        
    if not cmd:
        summary = "No supported programming language or test framework detected. Skipping test execution."
        logger.info(summary)
        return {
            "test_results": {
                "success": True,
                "framework": "none",
                "summary": summary,
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "failures": []
            },
            "build_logs": summary
        }

    logger.info(f"Detected framework: {framework}. Running test command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=120)
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ""
        stderr = (e.stderr or "") + f"\nTest execution timed out after 120 seconds."
        exit_code = -9
    except Exception as e:
        stdout = ""
        stderr = f"Failed to execute command: {str(e)}"
        exit_code = -1
        
    build_logs = f"--- Command: {' '.join(cmd)} ---\nExit Code: {exit_code}\n\n--- Standard Output ---\n{stdout}\n\n--- Standard Error ---\n{stderr}"
    
    success = (exit_code == 0)
    if framework == "pytest" and exit_code == 5:
        success = True  # No tests collected is treated as success in this context
        
    tests_run = 0
    tests_passed = 0
    tests_failed = 0
    failures = []
    
    if framework == "pytest":
        tests_run, tests_passed, tests_failed = parse_pytest_output(stdout + stderr)
    elif framework == "unittest":
        tests_run, tests_passed, tests_failed = parse_unittest_output(stdout + stderr)
        
    if not success and tests_failed == 0 and exit_code != 0:
        tests_failed = 1  # General failure
        failures.append(stderr or stdout or f"Command exited with code {exit_code}")
    elif tests_failed > 0:
        # Extract failures/errors from logs
        for line in (stdout + stderr).splitlines():
            if line.startswith("FAIL:") or line.startswith("ERROR:") or "Traceback" in line:
                failures.append(line)
        if not failures:
            failures.append("Test failures detected. Check build_logs for full details.")
            
    summary = f"Ran {tests_run} tests: {tests_passed} passed, {tests_failed} failed."
    logger.info(f"Test run finished. Success: {success}. {summary}")
    
    execution_history = list(state.get("execution_history", []))
    execution_history.append({
        "node": "tester_agent",
        "action": "run_tests",
        "framework": framework,
        "success": success,
        "summary": summary
    })
    
    return {
        "test_results": {
            "success": success,
            "framework": framework,
            "summary": summary,
            "tests_run": tests_run,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "failures": failures
        },
        "build_logs": build_logs,
        "execution_history": execution_history
    }
