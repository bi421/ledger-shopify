import os
from pathlib import Path

def create_trueroas_structure():
    """
    Automatically creates the TrueROAS project structure and initial files.
    """
    # Use the directory where the script is located as the project root
    root = Path(__file__).parent.resolve()
    
    print(f"🚀 Initializing TrueROAS project at: {root}")

    # 1. Define Directory Structure
    directories = [
        "src/trueroas/pipeline",
        "src/trueroas/math",
        "src/trueroas/ingestion",
        "src/trueroas/warehouse",
        "src/trueroas/api/routes",
        "data/raw",
        "data/clean",
        "config",
        "tests",
        "docker",
    ]

    # 2. Create Directories and __init__.py files
    for folder in directories:
        path = root / folder
        path.mkdir(parents=True, exist_ok=True)
        
        # Initialize as Python package if in src/
        if "src" in folder:
            (path / "__init__.py").touch()

    # Ensure the root package is initialized
    (root / "src" / "trueroas" / "__init__.py").touch()

    # 3. Define Initial File Content
    files_to_create = {
        "pyproject.toml": """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "trueroas"
version = "0.1.0"
description = "High-performance marketing truth engine"
requires-python = ">=3.11"
dependencies = [
    "polars>=1.0",
    "duckdb>=1.0",
    "fastapi",
    "uvicorn[standard]",
    "pydantic>=2.7",
    "pydantic-settings",
    "prefect>=2.14",
    "python-dotenv",
    "requests",
    "pyyaml",
    "pytest",
]
""",
        "src/trueroas/math/metrics.py": '"""Core marketing truth metrics."""\nimport polars as pl\n\n# Implementation follows...\n',
        "README.md": "# TrueROAS\nHigh-performance marketing truth engine.",
        ".gitignore": "__pycache__/\n*.py[cod]\n.env\ndata/\n*.duckdb\n",
    }

    # 4. Write Files
    for file_path, content in files_to_create.items():
        (root / file_path).write_text(content)
        print(f"✅ Created: {file_path}")

    print("\n✨ TrueROAS project skeleton is ready.")

if __name__ == "__main__":
    create_trueroas_structure()