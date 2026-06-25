"""
Tests for individual agents/nodes behavior and LangGraph state transitions.
"""
import os
import shutil
import unittest
from src.agents.parser import parse_repository
from src.utils.repository_intelligence import analyze_repository

class TestRepositoryIntelligence(unittest.TestCase):
    def setUp(self):
        # Setup temporary mock directory structure
        self.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp_test_repo"))
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
        # Write requirements.txt
        with open(os.path.join(self.test_dir, "requirements.txt"), "w") as f:
            f.write("fastapi>=0.100.0\npytest==7.4.0\n# comments and blank lines\n\nrequests\n")
            
        # Write package.json
        pkg_data = {
            "dependencies": {
                "react": "^18.2.0"
            },
            "devDependencies": {
                "typescript": "^5.0.0"
            }
        }
        import json
        with open(os.path.join(self.test_dir, "package.json"), "w") as f:
            json.dump(pkg_data, f)
            
        # Write python files
        with open(os.path.join(self.test_dir, "main.py"), "w") as f:
            f.write("print('Hello World')\n")
            
        # Write js files
        with open(os.path.join(self.test_dir, "index.js"), "w") as f:
            f.write("console.log('Hello JS')\n")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_analyze_repository(self):
        file_contents = {
            "requirements.txt": "fastapi>=0.100.0\npytest==7.4.0\nrequests\n",
            "package.json": '{"dependencies": {"react": "^18.2.0"}, "devDependencies": {"typescript": "^5.0.0"}}',
            "main.py": "print('Hello World')\n",
            "index.js": "console.log('Hello JS')\n"
        }
        repository_structure = {
            "files": ["requirements.txt", "package.json", "main.py", "index.js"],
            "directories": []
        }
        
        result = analyze_repository(self.test_dir, file_contents, repository_structure)
        
        self.assertIn("Python", result["languages"])
        self.assertIn("JavaScript", result["languages"])
        self.assertIn("JSON", result["languages"])
        
        self.assertIn("FastAPI", result["frameworks"])
        self.assertIn("pytest", result["frameworks"])
        self.assertIn("React", result["frameworks"])
        
        self.assertIn("fastapi", result["dependencies"])
        self.assertIn("pytest", result["dependencies"])
        self.assertIn("requests", result["dependencies"])
        self.assertIn("react", result["dependencies"])
        self.assertIn("typescript", result["dependencies"])
        
        metadata = result["project_metadata"]
        self.assertEqual(metadata["total_files"], 4)
        self.assertIn("pip (requirements.txt)", metadata["build_systems"])
        self.assertIn("npm/yarn/pnpm (package.json)", metadata["build_systems"])
        self.assertIn("main.py", metadata["entry_points"])
        self.assertIn("index.js", metadata["entry_points"])

    def test_parse_repository_node(self):
        state = {
            "repo_path": self.test_dir,
            "repo_url": "https://github.com/mock-user/mock-repo.git",
            "workspace_path": os.path.dirname(self.test_dir)
        }
        
        # Invoke parse_repository node
        updated_state = parse_repository(state)
        
        self.assertIn("languages", updated_state)
        self.assertIn("frameworks", updated_state)
        self.assertIn("dependencies", updated_state)
        self.assertIn("project_metadata", updated_state)
        
        self.assertIn("Python", updated_state["languages"])
        self.assertIn("FastAPI", updated_state["frameworks"])
        self.assertIn("react", updated_state["dependencies"])
        self.assertEqual(updated_state["project_metadata"]["total_files"], 4)
