"""Temporary script to find all variables in Python code files."""

import ast
from pathlib import Path
from typing import Any, Dict, List


def find_variables_in_file(filepath: str) -> list[Dict[str, Any]]:
    """Parse a Python file and extract all variable names with locations."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"ERROR parsing {filepath}: {e}")
        return []

    results: List[Dict[str, Any]] = []

    class VariableFinder(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                results.append(
                    {
                        "name": node.id,
                        "line": node.lineno,
                        "col": node.col_offset,
                        "type": "store" if isinstance(node.ctx, ast.Store) else "delete",
                    }
                )
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            # Add function arguments as variables
            for arg in node.args.args:
                results.append(
                    {
                        "name": arg.arg,
                        "line": node.lineno,
                        "col": node.col_offset,
                        "type": "argument",
                    }
                )
            self.generic_visit(node)

    VariableFinder().visit(tree)
    return results


def main() -> None:
    project_root = Path("C:\\Code\\XAAUSD-PAction-projectFolder")
    py_files = list(project_root.rglob("*.py"))

    all_variables: Dict[str, List[Dict[str, Any]]] = {}

    for py_file in py_files:
        rel_path = str(py_file.relative_to(project_root))
        variables = find_variables_in_file(str(py_file))
        for var in variables:
            name = var["name"]
            if name not in all_variables:
                all_variables[name] = []
            all_variables[name].append(
                {
                    "file": rel_path,
                    "line": var["line"],
                    "col": var["col"],
                    "type": var["type"],
                }
            )

    # Print all unique variable names sorted
    print(f"Found {len(all_variables)} unique variable names across {len(py_files)} Python files\n")
    for name in sorted(all_variables.keys()):
        occurrences = all_variables[name]
        print(f"{name} ({len(occurrences)} occurrences)")
        for occ in occurrences[:5]:  # Show first 5 occurrences
            print(f"  - {occ['file']}:{occ['line']} ({occ['type']})")
        if len(occurrences) > 5:
            print(f"  ... and {len(occurrences) - 5} more")


if __name__ == "__main__":
    main()
