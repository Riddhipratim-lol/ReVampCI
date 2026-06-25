"""
Tests for Phase 3 - Deep Code Analysis Engine.
"""
import os
import shutil
import unittest
from unittest.mock import patch

from src.utils.ast_parser import parse_file_to_ast, build_symbol_table, build_dependency_graph
from src.agents.analysis import analysis_agent
from src.graph import app
from src.config import settings

class TestPhase3Analysis(unittest.TestCase):
    def setUp(self):
        # Create temporary mock directory for testing imports & graph
        self.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp_analysis_repo"))
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_parse_python_ast(self):
        code = (
            "import os\n"
            "from src.state import GraphState\n"
            "from .utils import get_logger\n\n"
            "class MyCalculator:\n"
            "    def __init__(self, start=0):\n"
            "        self.val = start\n\n"
            "    def add_values(self, a: int, b=5) -> int:\n"
            "        return a + b\n\n"
            "def global_helper(x, *args):\n"
            "    return x\n"
        )
        
        ast_result = parse_file_to_ast("math_helper.py", code)
        
        # Check imports
        self.assertIn("os", ast_result["imports"])
        self.assertIn("src.state", ast_result["imports"])
        self.assertIn(".utils", ast_result["imports"])
        
        # Check classes
        self.assertEqual(len(ast_result["classes"]), 1)
        cls = ast_result["classes"][0]
        self.assertEqual(cls["name"], "MyCalculator")
        
        # Check methods
        methods = cls["methods"]
        self.assertEqual(len(methods), 2)
        self.assertEqual(methods[0]["name"], "__init__")
        self.assertIn("self", methods[0]["parameters"])
        self.assertIn("start", methods[0]["parameters"])
        
        self.assertEqual(methods[1]["name"], "add_values")
        self.assertIn("self", methods[1]["parameters"])
        self.assertIn("a", methods[1]["parameters"])
        self.assertIn("b", methods[1]["parameters"])
        
        # Check global functions
        self.assertEqual(len(ast_result["functions"]), 1)
        func = ast_result["functions"][0]
        self.assertEqual(func["name"], "global_helper")
        self.assertIn("x", func["parameters"])
        self.assertIn("args", func["parameters"])

    def test_parse_js_ast(self):
        code = (
            "import { config } from './config';\n"
            "const db = require('../database');\n\n"
            "class User {\n"
            "    constructor(id) {\n"
            "        this.id = id;\n"
            "    }\n"
            "    getName() {}\n"
            "}\n\n"
            "function computeTotal(items) {}\n"
        )
        
        ast_result = parse_file_to_ast("user.js", code)
        
        # Check imports
        self.assertIn("./config", ast_result["imports"])
        self.assertIn("../database", ast_result["imports"])
        
        # Check classes
        self.assertEqual(len(ast_result["classes"]), 1)
        self.assertEqual(ast_result["classes"][0]["name"], "User")
        self.assertEqual(len(ast_result["classes"][0]["methods"]), 2)
        self.assertEqual(ast_result["classes"][0]["methods"][0]["name"], "constructor")
        self.assertEqual(ast_result["classes"][0]["methods"][1]["name"], "getName")
        
        # Check functions
        self.assertEqual(len(ast_result["functions"]), 1)
        self.assertEqual(ast_result["functions"][0]["name"], "computeTotal")

    def test_build_symbol_table(self):
        ast_data = {
            "math_helper.py": {
                "classes": [
                    {
                        "name": "MyCalculator",
                        "start_line": 4,
                        "end_line": 9,
                        "methods": [
                            {"name": "add_values", "start_line": 7, "end_line": 9, "parameters": ["self", "a", "b"]}
                        ]
                    }
                ],
                "functions": [
                    {"name": "global_helper", "start_line": 11, "end_line": 12, "parameters": ["x"]}
                ]
            }
        }
        
        sym_table = build_symbol_table(ast_data)
        
        self.assertIn("MyCalculator", sym_table)
        self.assertEqual(sym_table["MyCalculator"][0]["kind"], "class")
        self.assertEqual(sym_table["MyCalculator"][0]["file"], "math_helper.py")
        
        self.assertIn("add_values", sym_table)
        self.assertEqual(sym_table["add_values"][0]["kind"], "method")
        self.assertEqual(sym_table["add_values"][0]["container"], "MyCalculator")
        
        self.assertIn("global_helper", sym_table)
        self.assertEqual(sym_table["global_helper"][0]["kind"], "function")

    def test_build_dependency_graph(self):
        files = [
            "src/state.py",
            "src/utils/logger.py",
            "src/agents/parser.py",
            "src/agents/analysis.py"
        ]
        
        file_contents = {
            "src/agents/analysis.py": "from src.state import GraphState\nfrom ..utils.logger import get_logger\n",
            "src/agents/parser.py": "from src.state import GraphState\n",
            "src/utils/logger.py": "import os\n",
            "src/state.py": "from typing import TypedDict\n"
        }
        
        ast_data = {
            "src/agents/analysis.py": {
                "classes": [], "functions": [], "imports": ["src.state", "..utils.logger"]
            },
            "src/agents/parser.py": {
                "classes": [], "functions": [], "imports": ["src.state"]
            },
            "src/utils/logger.py": {
                "classes": [], "functions": [], "imports": ["os"]
            },
            "src/state.py": {
                "classes": [], "functions": [], "imports": []
            }
        }
        
        dep_graph = build_dependency_graph(self.test_dir, files, file_contents, ast_data)
        
        # Verify src/agents/analysis.py dependencies
        analysis_deps = dep_graph["src/agents/analysis.py"]
        self.assertIn("src/state.py", analysis_deps)
        self.assertIn("src/utils/logger.py", analysis_deps)
        
        # Verify src/agents/parser.py dependencies
        parser_deps = dep_graph["src/agents/parser.py"]
        self.assertIn("src/state.py", parser_deps)

    @patch("src.agents.codespace.validate_github_url")
    @patch("src.agents.codespace.clone_repository")
    def test_end_to_end_flow_with_analysis(self, mock_clone, mock_validate):
        mock_validate.return_value = True
        
        # Setup files inside temp directory (outside CLONES_DIR)
        temp_src_dir = os.path.join(settings.WORKSPACE_ROOT, "tests", "temp_mock_analysis_src")
        if os.path.exists(temp_src_dir):
            shutil.rmtree(temp_src_dir)
        os.makedirs(temp_src_dir)
        
        calc_path = os.path.join(temp_src_dir, "calculator.py")
        with open(calc_path, "w", encoding="utf-8") as f:
            f.write(
                "import os\n\n"
                "class SimpleCalculator:\n"
                "    def add(self, a, b):\n"
                "        return a + b\n"
            )
            
        def side_effect_clone(url, dest):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(temp_src_dir, dest)
            
        mock_clone.side_effect = side_effect_clone
        
        initial_state = {
            "repo_url": "https://github.com/mock-user/mock-analysis-repo.git"
        }
        
        # We also need to make sure the clones dest is cleaned up afterwards
        clones_dest = os.path.join(settings.CLONES_DIR, "mock-analysis-repo")
        if os.path.exists(clones_dest):
            shutil.rmtree(clones_dest)
            
        try:
            final_state = app.invoke(initial_state)
        finally:
            if os.path.exists(temp_src_dir):
                shutil.rmtree(temp_src_dir)
            if os.path.exists(clones_dest):
                shutil.rmtree(clones_dest)
        
        # Verify analysis agent outputs in the final state
        self.assertIn("ast_data", final_state)
        self.assertIn("dependency_graph", final_state)
        self.assertIn("symbol_table", final_state)
        
        # Verify exact parsed contents of calculator.py
        ast_data = final_state["ast_data"]
        self.assertIn("calculator.py", ast_data)
        
        classes = ast_data["calculator.py"]["classes"]
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0]["name"], "SimpleCalculator")
        self.assertEqual(classes[0]["methods"][0]["name"], "add")
        
        # Verify symbol table index
        sym_table = final_state["symbol_table"]
        self.assertIn("SimpleCalculator", sym_table)
        self.assertEqual(sym_table["SimpleCalculator"][0]["file"], "calculator.py")
        self.assertEqual(sym_table["SimpleCalculator"][0]["kind"], "class")

