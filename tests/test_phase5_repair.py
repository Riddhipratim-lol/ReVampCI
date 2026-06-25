import os
import shutil
import unittest
from unittest.mock import patch, MagicMock
from src.state import GraphState
from src.agents.repair import repair_node, RepairOutputSchema, RepairedFile
from src.graph import app, should_continue
from src.config import settings

class TestPhase5Repair(unittest.TestCase):
    def setUp(self):
        # Create a mock repository directory structure for testing
        self.mock_repo_dir = os.path.join(settings.WORKSPACE_ROOT, "tests", "mock_repo_phase5")
        if os.path.exists(self.mock_repo_dir):
            shutil.rmtree(self.mock_repo_dir)
        os.makedirs(self.mock_repo_dir)
        
        self.file_path = os.path.join(self.mock_repo_dir, "calculator.py")
        with open(self.file_path, "w", encoding="utf-8") as f:
            # Code with intentional bug
            f.write(
                "def add(a, b):\n"
                "    return a - b  # Bug: subtraction instead of addition\n"
            )

    def tearDown(self):
        if os.path.exists(self.mock_repo_dir):
            shutil.rmtree(self.mock_repo_dir)
            
        cloned_dest = os.path.join(settings.CLONES_DIR, "mock-repo-phase5")
        if os.path.exists(cloned_dest):
            shutil.rmtree(cloned_dest)

    @patch("src.agents.repair.init_chat_model")
    def test_repair_node_isolation(self, mock_init_chat_model):
        # Configure mock LLM response
        mock_model = MagicMock()
        mock_init_chat_model.return_value = mock_model
        mock_model.with_structured_output.return_value = mock_model
        
        # Prepare structured repair output
        repaired_file = RepairedFile(
            filepath="calculator.py",
            new_content="def add(a, b):\n    return a + b\n",
            change_description="Fixed the subtraction bug to perform addition."
        )
        mock_model.invoke.return_value = RepairOutputSchema(
            repaired_files=[repaired_file],
            explanation="The add function was mistakenly subtracting instead of adding."
        )
        
        # Prepare state
        initial_state = {
            "repo_path": self.mock_repo_dir,
            "file_contents": {
                "calculator.py": "def add(a, b):\n    return a - b  # Bug: subtraction instead of addition\n"
            },
            "test_results": {
                "success": False,
                "framework": "pytest",
                "summary": "Ran 1 tests: 0 passed, 1 failed.",
                "tests_run": 1,
                "tests_passed": 0,
                "tests_failed": 1,
                "failures": ["AssertionError: -1 != 3"]
            },
            "build_logs": "AssertionError in test_add: expected 3, got -1",
            "repair_attempts": 0,
            "repair_history": [],
            "modified_files": [],
            "execution_history": []
        }
        
        # Run node
        result_state = repair_node(initial_state)
        
        # Assertions
        self.assertEqual(result_state["repair_attempts"], 1)
        self.assertEqual(len(result_state["repair_history"]), 1)
        self.assertEqual(result_state["repair_history"][0]["attempt"], 1)
        self.assertEqual(result_state["repair_history"][0]["explanation"], "The add function was mistakenly subtracting instead of adding.")
        self.assertIn("calculator.py", result_state["modified_files"])
        self.assertIn("calculator.py", result_state["file_contents"])
        self.assertEqual(result_state["file_contents"]["calculator.py"], "def add(a, b):\n    return a + b\n")
        
        # Verify changes written to disk
        with open(self.file_path, "r", encoding="utf-8") as f:
            disk_content = f.read()
        self.assertEqual(disk_content, "def add(a, b):\n    return a + b\n")

    def test_should_continue_routing(self):
        # 1. Success case -> report_node
        state_success = {
            "test_results": {"success": True},
            "repair_attempts": 0
        }
        self.assertEqual(should_continue(state_success), "report_node")
        
        # 2. Failure with attempts < 3 -> repair_node
        state_fail_1 = {
            "test_results": {"success": False},
            "repair_attempts": 1
        }
        self.assertEqual(should_continue(state_fail_1), "repair_node")
        
        # 3. Failure with attempts >= 3 -> report_node
        state_fail_3 = {
            "test_results": {"success": False},
            "repair_attempts": 3
        }
        self.assertEqual(should_continue(state_fail_3), "report_node")

    @patch("src.agents.codespace.validate_github_url")
    @patch("src.agents.codespace.clone_repository")
    @patch("src.agents.codespace.prepare_environment")
    @patch("src.agents.critic.init_chat_model")
    @patch("src.agents.coding.init_chat_model")
    @patch("src.agents.tester.subprocess.run")
    @patch("src.agents.repair.init_chat_model")
    @patch("src.agents.report.init_chat_model")
    def test_validation_loop_workflow(
        self, mock_report_model, mock_repair_model, mock_subproc, mock_coding_model, mock_critic_model, mock_prep, mock_clone, mock_validate
    ):
        mock_validate.return_value = True
        
        # Copy mock repo instead of cloning
        def side_effect_clone(url, dest):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(self.mock_repo_dir, dest)
        mock_clone.side_effect = side_effect_clone
        
        # Mock Critic output
        mock_critic = MagicMock()
        mock_critic_model.return_value = mock_critic
        mock_critic.with_structured_output.return_value = mock_critic
        mock_critic.invoke.return_value = MagicMock(
            identified_issues=["Subtraction bug in calculator.py"],
            refactoring_tasks=["Fix add function"],
            priority_rankings=[MagicMock(task="Fix add function", priority="HIGH", effort="LOW", impact="Fix addition", file="calculator.py")],
            maintainability_score=90
        )
        
        # Mock Coding output
        mock_coding = MagicMock()
        mock_coding_model.return_value = mock_coding
        mock_coding.with_structured_output.return_value = mock_coding
        mock_coding.invoke.return_value = MagicMock(
            modified_files=[MagicMock(filepath="calculator.py", new_content="def add(a, b):\n    return a - b\n", change_description="Tried to fix addition")]
        )
        
        # Mock Subprocess Run for testing node:
        # First call (after refactor) -> Fails
        # Second call (after repair) -> Passes
        mock_proc_fail = MagicMock(returncode=1, stdout="=== 1 failed in 0.01s ===", stderr="AssertionError: -1 != 3")
        mock_proc_pass = MagicMock(returncode=0, stdout="=== 1 passed in 0.01s ===", stderr="")
        mock_subproc.side_effect = [mock_proc_fail, mock_proc_pass]
        
        # Mock Repair output
        mock_repair = MagicMock()
        mock_repair_model.return_value = mock_repair
        mock_repair.with_structured_output.return_value = mock_repair
        repaired_file = RepairedFile(
            filepath="calculator.py",
            new_content="def add(a, b):\n    return a + b\n",
            change_description="Fixed add function to add instead of subtract."
        )
        mock_repair.invoke.return_value = MagicMock(
            repaired_files=[repaired_file],
            explanation="Corrected subtraction operator to addition."
        )
        
        # Mock Report output
        mock_report = MagicMock()
        mock_report_model.return_value = mock_report
        mock_report.invoke.return_value = MagicMock(content="Mocked Executive Summary")
        
        # Run graph
        initial_state = {
            "repo_url": "https://github.com/mock-user/mock-repo-phase5.git"
        }
        
        final_state = app.invoke(initial_state)
        
        # Verify validation loop run
        self.assertIn("repair_attempts", final_state)
        self.assertEqual(final_state["repair_attempts"], 1)
        self.assertEqual(len(final_state["repair_history"]), 1)
        self.assertEqual(final_state["repair_history"][0]["explanation"], "Corrected subtraction operator to addition.")
        
        # Verify final status
        self.assertTrue(final_state["test_results"]["success"])
        self.assertIn("calculator.py", final_state["modified_files"])
        self.assertIn("Autonomous Repair Attempts", final_state["final_report"])
        self.assertIn("Attempt 1", final_state["final_report"])
        
if __name__ == "__main__":
    unittest.main()
