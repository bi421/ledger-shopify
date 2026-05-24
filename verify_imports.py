import ast
import os
import sys
from pathlib import Path


def verify_namespace_standard(root_dir: str):
    """
    Scan the project for internal imports that bypass the expected src.trueroas namespace.
    """
    violations = []
    target_package = "trueroas"

    skip_dirs = {".venv", "venv", "__pycache__", ".git", "build", "dist"}

    print(f"[check] Auditing namespace consistency in: {root_dir}")

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            if not file.endswith(".py") or file == "verify_imports.py":
                continue

            file_path = Path(root) / file
            relative_path = file_path.relative_to(root_dir)

            try:
                with open(file_path, "r", encoding="utf-8-sig") as f:
                    tree = ast.parse(f.read())
            except Exception as exc:
                print(f"[warn] Could not parse {relative_path}: {exc}")
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == target_package or alias.name.startswith(f"{target_package}."):
                            violations.append((relative_path, node.lineno, alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith(target_package):
                        violations.append((relative_path, node.lineno, node.module))

    if violations:
        print("\n[fail] Namespace violations found! Use 'src.trueroas' instead of 'trueroas':")
        print("-" * 80)
        for path, line, module in violations:
            print(f"File: {path}:{line} -> Found: '{module}'")
        print("-" * 80)
        print(f"Total violations: {len(violations)}")
        return False

    print("\n[ok] All internal imports follow the 'src.trueroas' namespace convention.")
    return True


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.abspath(__file__))
    success = verify_namespace_standard(project_root)
    sys.exit(0 if success else 1)
