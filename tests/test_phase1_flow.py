import os
import shutil
import unittest
from unittest.mock import patch
from src.graph import app
from src.config import settings

class TestPhase1Flow(unittest.TestCase):
    def setUp(self):
        # Create a mock repository directory structure for testing
        self.mock_repo_dir = os.path.join(settings.WORKSPACE_ROOT, "tests", "mock_repo")
        if os.path.exists(self.mock_repo_dir):
            shutil.rmtree(self.mock_repo_dir)
        os.makedirs(self.mock_repo_dir)
        
        # Write some files with intentional code smells (e.g. unused import, poor naming)
        self.file1_path = os.path.join(self.mock_repo_dir, "calculator.py")
        with open(self.file1_path, "w", encoding="utf-8") as f:
            f.write(
                "import os\n"
                "import sys\n\n"
                "def ADD_NUMBERS_TOGETHER(a, b):\n"
                "    # Poor naming and unused imports\n"
                "    result = a + b\n"
                "    return result\n"
            )
            
        self.file2_path = os.path.join(self.mock_repo_dir, "utils.py")
        with open(self.file2_path, "w", encoding="utf-8") as f:
            f.write(
                "def unused_function():\n"
                "    pass\n"
            )

    def tearDown(self):
        if os.path.exists(self.mock_repo_dir):
            shutil.rmtree(self.mock_repo_dir)
            
        # Also clean up clones dir for mock repo if cloned there
        cloned_dest = os.path.join(settings.CLONES_DIR, "mock-repo")
        if os.path.exists(cloned_dest):
            shutil.rmtree(cloned_dest)

    @patch("src.agents.codespace.validate_github_url")
    @patch("src.agents.codespace.clone_repository")
    def test_end_to_end_flow(self, mock_clone, mock_validate):
        mock_validate.return_value = True
        
        # Define clone behavior to copy mock repo instead of cloning
        def side_effect_clone(url, dest):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(self.mock_repo_dir, dest)
            
        mock_clone.side_effect = side_effect_clone
        
        # Run graph
        initial_state = {
            "repo_url": "https://github.com/mock-user/mock-repo.git"
        }
        
        print("\nInvoking LangGraph flow...")
        final_state = app.invoke(initial_state)
        print("Flow finished.")
        
        # Assertions
        self.assertIn("repo_path", final_state)
        self.assertTrue(os.path.exists(final_state["repo_path"]))
        
        self.assertIn("file_contents", final_state)
        self.assertIn("calculator.py", final_state["file_contents"])
        
        self.assertIn("identified_issues", final_state)
        self.assertGreater(len(final_state["identified_issues"]), 0)
        print("\nIdentified Issues:")
        for issue in final_state["identified_issues"]:
            print(f"- {issue}")
        
        self.assertIn("refactoring_tasks", final_state)
        self.assertGreater(len(final_state["refactoring_tasks"]), 0)
        print("\nRefactoring Tasks:")
        for task in final_state["refactoring_tasks"]:
            print(f"- {task}")
        
        self.assertIn("modified_files", final_state)
        self.assertGreater(len(final_state["modified_files"]), 0)
        print("\nModified Files:")
        for file in final_state["modified_files"]:
            print(f"- {file}")
        
        # Verify that changes were saved to disk
        dest_calc_path = os.path.join(final_state["repo_path"], "calculator.py")
        with open(dest_calc_path, "r", encoding="utf-8") as f:
            refactored_content = f.read()
            
        print("\nRefactored calculator.py content:")
        print(refactored_content)
        
        # Verify that the poorly-named function name was improved (i.e. no longer ADD_NUMBERS_TOGETHER)
        self.assertNotIn("def ADD_NUMBERS_TOGETHER", refactored_content)
        
        # Check execution history trace
        self.assertIn("execution_history", final_state)
        self.assertGreater(len(final_state["execution_history"]), 0)
        print("\nExecution History:")
        for trace in final_state["execution_history"]:
            print(trace)

if __name__ == "__main__":
    unittest.main()
