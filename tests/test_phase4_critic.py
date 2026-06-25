"""
Tests for Phase 4 - Senior Architect Critic.
"""
import unittest
from unittest.mock import patch, MagicMock

from src.utils.architecture_critic import (
    detect_circular_dependencies,
    detect_large_classes,
    detect_high_complexity_modules,
    detect_architectural_violations,
    calculate_maintainability_score
)
from src.agents.critic import critic_node, CriticOutputSchema, PriorityRankingItem

class TestPhase4Critic(unittest.TestCase):
    def test_detect_circular_dependencies_cyclic(self):
        # A simple cycle: a -> b -> c -> a
        dep_graph = {
            "src/a.py": ["src/b.py"],
            "src/b.py": ["src/c.py"],
            "src/c.py": ["src/a.py", "src/d.py"],
            "src/d.py": []
        }
        cycles = detect_circular_dependencies(dep_graph)
        self.assertEqual(len(cycles), 1)
        # Check cycle nodes
        cycle = cycles[0]
        self.assertEqual(cycle[0], cycle[-1])  # Starts and ends at same node
        self.assertIn("src/a.py", cycle)
        self.assertIn("src/b.py", cycle)
        self.assertIn("src/c.py", cycle)
        self.assertNotIn("src/d.py", cycle)

    def test_detect_circular_dependencies_acyclic(self):
        dep_graph = {
            "src/a.py": ["src/b.py"],
            "src/b.py": ["src/c.py"],
            "src/c.py": []
        }
        cycles = detect_circular_dependencies(dep_graph)
        self.assertEqual(len(cycles), 0)

    def test_detect_large_classes(self):
        ast_data = {
            "src/big.py": {
                "classes": [
                    {
                        "name": "GiantClass",
                        "start_line": 10,
                        "end_line": 200,  # 191 lines (violates 150 threshold)
                        "methods": [{"name": f"method_{i}"} for i in range(5)]
                    },
                    {
                        "name": "NormalClass",
                        "start_line": 20,
                        "end_line": 50,
                        "methods": []
                    }
                ],
                "functions": []
            }
        }
        large = detect_large_classes(ast_data, line_threshold=150, method_threshold=8)
        self.assertEqual(len(large), 1)
        self.assertEqual(large[0]["class_name"], "GiantClass")
        self.assertEqual(large[0]["file"], "src/big.py")

    def test_detect_high_complexity_modules(self):
        ast_data = {
            "src/complex.py": {
                "classes": [
                    {
                        "name": "C1",
                        "methods": [{"name": f"m{i}"} for i in range(6)]
                    }
                ],
                "functions": [{"name": f"f{i}"} for i in range(5)]  # total 11
            },
            "src/simple.py": {
                "classes": [],
                "functions": []
            }
        }
        complex_mods = detect_high_complexity_modules(ast_data, function_threshold=10)
        self.assertEqual(len(complex_mods), 1)
        self.assertEqual(complex_mods[0]["file"], "src/complex.py")
        self.assertEqual(complex_mods[0]["total_functions"], 11)

    def test_detect_architectural_violations(self):
        # src/utils/logger.py imports src/agents/critic.py -> violation!
        # src/agents/parser.py imports src/graph.py -> violation!
        dep_graph = {
            "src/utils/logger.py": ["src/agents/critic.py", "src/state.py"],
            "src/agents/parser.py": ["src/graph.py", "src/state.py"],
            "src/state.py": []
        }
        violations = detect_architectural_violations(dep_graph)
        self.assertEqual(len(violations), 2)
        
        viol_files = [v["file"] for v in violations]
        self.assertIn("src/utils/logger.py", viol_files)
        self.assertIn("src/agents/parser.py", viol_files)

    def test_calculate_maintainability_score(self):
        # perfect score
        score = calculate_maintainability_score([], [], [], [])
        self.assertEqual(score, 100)
        
        # some deductions
        score = calculate_maintainability_score(
            cycles=[["a", "b", "a"]],
            violations=[{"file": "a"}],
            large_classes=[{"class_name": "Giant"}],
            complex_modules=[]
        )
        # 100 - 15 - 10 - 5 = 70
        self.assertEqual(score, 70)

    @patch("src.agents.critic.init_chat_model")
    def test_critic_node_integration(self, mock_init_chat_model):
        # Mock LLM and structured output
        mock_model = MagicMock()
        mock_init_chat_model.return_value = mock_model
        
        mock_output = CriticOutputSchema(
            identified_issues=["Large class detected", "Layering boundary violation"],
            refactoring_tasks=["Extract methods from LargeClass"],
            priority_rankings=[
                PriorityRankingItem(
                    task="Extract methods from LargeClass",
                    priority="HIGH",
                    effort="LOW",
                    impact="Reduces size of giant class",
                    file="src/big.py"
                )
            ],
            maintainability_score=85
        )
        mock_model.with_structured_output.return_value.invoke.return_value = mock_output
        
        # Run critic node with mock state
        state = {
            "repo_url": "https://github.com/mock/mock.git",
            "repo_path": "/mock/path",
            "workspace_path": "/mock",
            "file_contents": {
                "src/big.py": "class LargeClass:\n    pass\n"
            },
            "repository_structure": {
                "files": ["src/big.py"],
                "directories": ["src"]
            },
            "ast_data": {
                "src/big.py": {
                    "classes": [{"name": "LargeClass", "start_line": 1, "end_line": 2, "methods": []}],
                    "functions": []
                }
            },
            "dependency_graph": {
                "src/big.py": []
            }
        }
        
        result = critic_node(state)
        
        self.assertEqual(result["maintainability_score"], 85)
        self.assertEqual(len(result["priority_rankings"]), 1)
        self.assertEqual(result["priority_rankings"][0]["priority"], "HIGH")
        self.assertEqual(result["priority_rankings"][0]["file"], "src/big.py")
        self.assertIn("Large class detected", result["identified_issues"])
