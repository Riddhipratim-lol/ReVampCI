import sys
import os
from dotenv import load_dotenv

# Ensure env variables are loaded
load_dotenv()

# Sync GOOGLE_API_KEY with GEMINI_API_KEY
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

from src.graph import app

def main():
    # Accept URL from command-line arguments or prompt user
    if len(sys.argv) > 1:
        repo_url = sys.argv[1]
    else:
        repo_url = input("Enter the GitHub repository URL to refactor: ").strip()
        
    if not repo_url:
        print("Error: No repository URL provided.")
        sys.exit(1)
        
    print(f"\n[ReVampCI] Starting autonomous refactoring for: {repo_url}\n")
    
    try:
        initial_state = {"repo_url": repo_url}
        final_state = app.invoke(initial_state)
        
        report = final_state.get("final_report", "No report generated.")
        print("\n" + "=" * 50)
        print("FINAL REFACTORING REPORT")
        print("=" * 50)
        print(report)
        print("=" * 50 + "\n")
        
    except Exception as e:
        print(f"\n[Error] Workflow execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
