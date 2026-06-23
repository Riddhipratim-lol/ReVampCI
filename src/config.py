"""
Configuration loader for ReVampCI.
Loads variables from .env file and sets up workspace-level settings.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Sync GOOGLE_API_KEY with GEMINI_API_KEY for langchain_google_genai / google-genai
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

class Config:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    CUSTOM_GITHUB_TOKEN: str = os.getenv("CUSTOM_GITHUB_TOKEN", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///revampci.db")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Models to use
    CRITIC_MODEL: str = os.getenv("CRITIC_MODEL", "gemini-3.5-flash")
    REFACTOR_MODEL: str = os.getenv("REFACTOR_MODEL", "gemini-3.1-flash-lite")
    
    # Base directory for repository clones inside the workspace root
    # Automatically calculates the main project folder by finding where 
    # this script lives and moving one level up, making paths work on any computer.
    WORKSPACE_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    #uses the path to create a folder named 'workspace_clones' to store the cloned repositories
    CLONES_DIR: str = os.path.join(WORKSPACE_ROOT, "workspace_clones")

settings = Config()
